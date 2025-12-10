"""Segment Arbiter - Authoritative segment boundary resolution.

This module provides the SegmentArbiter class that acts as the authoritative
source of truth for segment boundaries in the transcription pipeline. It resolves
the double-chunking issue where both VAD and the ASR engine apply their own
segmentation logic, leading to overlapping and fragmented segments.

The arbiter treats ASR engine output as 'proposals' and produces clean,
non-overlapping, semantically coherent final segments by:

1. De-duplicating overlapping segments using LCS alignment
2. Merging tiny fragments into adjacent segments
3. Enforcing punctuation-aware boundaries
4. Handling silence gaps intelligently
"""

from __future__ import annotations

from typing import Sequence

from vociferous.domain.model import TranscriptSegment


# Punctuation constants for boundary detection
SENTENCE_PUNCTUATION = ".?!"
OTHER_PUNCTUATION = ".,!?;: \t\n"
CONNECTOR_WORDS = {"and", "but", "so", "or", "yet", "nor"}


def _lcs_length(text1: str, text2: str) -> int:
    """Calculate the length of the longest common subsequence of two strings.
    
    Uses word-level comparison for robustness against minor transcription differences.
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Length of the longest common subsequence in words
    """
    words1 = text1.lower().split()
    words2 = text2.lower().split()
    
    if not words1 or not words2:
        return 0
    
    # Classic LCS dynamic programming
    m, n = len(words1), len(words2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if words1[i - 1] == words2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    
    return dp[m][n]


def _word_count(text: str) -> int:
    """Count words in text, ignoring punctuation."""
    return len(text.split())


def _ends_with_sentence_punctuation(text: str) -> bool:
    """Check if text ends with sentence-ending punctuation."""
    text = text.rstrip()
    return len(text) > 0 and text[-1] in SENTENCE_PUNCTUATION


def _starts_with_connector(text: str) -> bool:
    """Check if text starts with a connector word."""
    text = text.lstrip()
    if not text:
        return False
    words = text.split()
    if not words:
        return False
    first_word = words[0].lower().rstrip(OTHER_PUNCTUATION)
    return first_word in CONNECTOR_WORDS


def _ends_with_lowercase(text: str) -> bool:
    """Check if text ends with a lowercase word without sentence punctuation (likely mid-phrase).
    
    If text has sentence-ending punctuation, it's not mid-phrase even if the word before
    punctuation is lowercase.
    """
    # First check for sentence-ending punctuation
    if _ends_with_sentence_punctuation(text):
        return False
    
    # No sentence punctuation, check if last word is lowercase
    text = text.rstrip(OTHER_PUNCTUATION)
    if not text:
        return False
    # Get last word
    words = text.split()
    if not words:
        return False
    last_word = words[-1]
    return bool(last_word) and last_word[0].islower()


def _find_overlap_words(seg1_text: str, seg2_text: str) -> int:
    """Find number of overlapping words at end of seg1 and start of seg2.
    
    Uses LCS to detect duplicate text even with minor transcription variations.
    
    Args:
        seg1_text: Text from first segment
        seg2_text: Text from second segment
        
    Returns:
        Number of overlapping words to remove from seg1
    """
    words1 = seg1_text.split()
    words2 = seg2_text.split()
    
    if not words1 or not words2:
        return 0
    
    # Try progressively longer suffixes of seg1 against prefixes of seg2
    max_overlap = 0
    for i in range(len(words1)):
        suffix = " ".join(words1[i:])
        # Check if this suffix appears at start of seg2
        lcs = _lcs_length(suffix, seg2_text)
        suffix_words = suffix.split()
        overlap_ratio = lcs / len(suffix_words) if suffix_words else 0
        # If significant overlap (>50% LCS match), consider it duplicate
        if overlap_ratio > 0.5:
            overlap_words = len(words1) - i
            max_overlap = max(max_overlap, overlap_words)
    
    return max_overlap


class SegmentArbiter:
    """Authoritative segment boundary arbiter.
    
    Treats ASR engine output as 'proposals' and produces clean,
    non-overlapping, semantically coherent final segments.
    
    Args:
        min_segment_duration_s: Minimum segment duration in seconds (default: 1.0)
        min_segment_words: Minimum number of words in a segment (default: 4)
        hard_break_silence_s: Silence duration that forces a hard break (default: 1.5)
        soft_break_silence_s: Silence duration for soft breaks (default: 0.7)
        
    Example:
        >>> arbiter = SegmentArbiter()
        >>> segments = [
        ...     TranscriptSegment(text="These services", start_s=0.82, end_s=2.82, language="en", confidence=0.9),
        ...     TranscriptSegment(text="services here. I am", start_s=1.92, end_s=3.92, language="en", confidence=0.9),
        ...     TranscriptSegment(text="woefully", start_s=3.50, end_s=4.20, language="en", confidence=0.9),
        ...     TranscriptSegment(text="woefully unprepared for this.", start_s=4.00, end_s=6.50, language="en", confidence=0.9),
        ... ]
        >>> clean_segments = arbiter.arbitrate(segments)
        >>> len(clean_segments)
        2
    """
    
    def __init__(
        self,
        min_segment_duration_s: float = 1.0,
        min_segment_words: int = 4,
        hard_break_silence_s: float = 1.5,
        soft_break_silence_s: float = 0.7,
    ) -> None:
        self.min_segment_duration_s = min_segment_duration_s
        self.min_segment_words = min_segment_words
        self.hard_break_silence_s = hard_break_silence_s
        self.soft_break_silence_s = soft_break_silence_s
    
    def arbitrate(
        self,
        segments: Sequence[TranscriptSegment],
    ) -> list[TranscriptSegment]:
        """Process raw segments and return de-duplicated, merged output.
        
        Algorithm:
        1. Sort segments by start_s
        2. For each segment:
           a. If overlaps with previous: use LCS to find duplicate prefix, keep only novel suffix
           b. If gap to previous < soft_break_silence_s AND previous doesn't end with punctuation:
              - Merge into previous segment
           c. If segment is too short (duration < min AND words < min):
              - Merge into previous or next segment
        3. Post-pass: enforce punctuation boundaries
           - If segment ends mid-phrase (lowercase word, connector), extend to include next segment
        4. Return final non-overlapping segments with corrected timestamps
        
        Args:
            segments: Raw segments from ASR engine
            
        Returns:
            List of clean, non-overlapping segments
        """
        if not segments:
            return []
        
        # Sort by start time
        sorted_segs = sorted(segments, key=lambda s: s.start_s)
        
        # Pass 1: De-duplicate overlaps
        deduped = self._deduplicate_overlaps(sorted_segs)
        
        # Pass 2: Merge tiny fragments
        merged = self._merge_tiny_fragments(deduped)
        
        # Pass 3: Enforce punctuation boundaries
        final = self._enforce_punctuation_boundaries(merged)
        
        return final
    
    def _deduplicate_overlaps(
        self,
        segments: Sequence[TranscriptSegment],
    ) -> list[TranscriptSegment]:
        """Remove overlapping duplicate text between consecutive segments.
        
        When segments overlap in time, detect duplicate text using LCS and keep
        only the novel portions.
        """
        if not segments:
            return []
        
        result: list[TranscriptSegment] = []
        
        for seg in segments:
            if not result:
                result.append(seg)
                continue
            
            prev = result[-1]
            
            # Check for time overlap
            if seg.start_s < prev.end_s:
                # Segments overlap in time - check for duplicate text
                overlap_words = _find_overlap_words(prev.text, seg.text)
                
                if overlap_words > 0:
                    # Remove duplicate words from previous segment
                    prev_words = prev.text.split()
                    if overlap_words >= len(prev_words):
                        # Previous segment is entirely contained in current - skip it
                        result[-1] = seg
                        continue
                    
                    # Keep only non-overlapping portion of previous segment
                    new_prev_text = " ".join(prev_words[:-overlap_words])
                    if new_prev_text.strip():
                        result[-1] = TranscriptSegment(
                            text=new_prev_text,
                            start_s=prev.start_s,
                            end_s=seg.start_s,  # Adjust end to where overlap starts
                            language=prev.language,
                            confidence=prev.confidence,
                        )
                        result.append(seg)
                    else:
                        # Previous segment was all overlap - replace it
                        result[-1] = seg
                else:
                    # Time overlap but no text overlap - keep both
                    result.append(seg)
            else:
                # No time overlap
                result.append(seg)
        
        return result
    
    def _merge_tiny_fragments(
        self,
        segments: Sequence[TranscriptSegment],
    ) -> list[TranscriptSegment]:
        """Merge segments that are too short into adjacent segments.
        
        Segments < min_segment_duration_s AND < min_segment_words are absorbed
        into neighbors (exception: segments at the very beginning or end).
        """
        if not segments:
            return []
        
        result: list[TranscriptSegment] = []
        i = 0
        
        while i < len(segments):
            seg = segments[i]
            duration = seg.end_s - seg.start_s
            word_count = _word_count(seg.text)
            
            # Check if segment is too small
            is_tiny = (
                duration < self.min_segment_duration_s
                and word_count < self.min_segment_words
            )
            
            # Don't merge if it's the only segment or at boundaries without neighbors
            if is_tiny and len(segments) > 1:
                # Try to merge with previous segment
                if result:
                    prev = result[-1]
                    gap = seg.start_s - prev.end_s
                    
                    # Merge if gap is small enough
                    if gap < self.hard_break_silence_s:
                        merged_text = prev.text + " " + seg.text
                        result[-1] = TranscriptSegment(
                            text=merged_text,
                            start_s=prev.start_s,
                            end_s=seg.end_s,
                            language=prev.language,
                            confidence=min(prev.confidence, seg.confidence),
                        )
                        i += 1
                        continue
                
                # Try to merge with next segment
                if i + 1 < len(segments):
                    next_seg = segments[i + 1]
                    gap = next_seg.start_s - seg.end_s
                    
                    if gap < self.hard_break_silence_s:
                        # Merge current with next
                        merged_text = seg.text + " " + next_seg.text
                        merged_seg = TranscriptSegment(
                            text=merged_text,
                            start_s=seg.start_s,
                            end_s=next_seg.end_s,
                            language=seg.language,
                            confidence=min(seg.confidence, next_seg.confidence),
                        )
                        result.append(merged_seg)
                        i += 2  # Skip next segment as we merged it
                        continue
            
            # Keep segment as is
            result.append(seg)
            i += 1
        
        return result
    
    def _enforce_punctuation_boundaries(
        self,
        segments: Sequence[TranscriptSegment],
    ) -> list[TranscriptSegment]:
        """Enforce punctuation-aware boundaries.
        
        If a segment ends mid-phrase (lowercase word, connector, or no punctuation),
        and there's a short gap to the next segment, merge them.
        """
        if len(segments) <= 1:
            return list(segments)
        
        result: list[TranscriptSegment] = []
        i = 0
        
        while i < len(segments):
            seg = segments[i]
            
            # Check if this segment should be merged with next
            if i + 1 < len(segments):
                next_seg = segments[i + 1]
                gap = next_seg.start_s - seg.end_s
                
                # Should merge if gap is short AND any of:
                # 1. Previous doesn't end with sentence punctuation
                # 2. Previous ends with lowercase (mid-phrase, overrides punctuation check)
                # 3. Next starts with connector (continuing thought after punctuation)
                has_sentence_end = _ends_with_sentence_punctuation(seg.text)
                has_lowercase_end = _ends_with_lowercase(seg.text)
                next_starts_connector = _starts_with_connector(next_seg.text)
                
                should_merge = (
                    gap < self.soft_break_silence_s
                    and (
                        has_lowercase_end  # Mid-phrase always merge
                        or next_starts_connector  # Connector always merge
                        or not has_sentence_end  # No sentence end = merge
                    )
                )
                
                if should_merge:
                    # Merge with next segment
                    merged_text = seg.text.rstrip() + " " + next_seg.text.lstrip()
                    merged_seg = TranscriptSegment(
                        text=merged_text,
                        start_s=seg.start_s,
                        end_s=next_seg.end_s,
                        language=seg.language,
                        confidence=min(seg.confidence, next_seg.confidence),
                    )
                    result.append(merged_seg)
                    i += 2  # Skip next segment as we merged it
                    continue
            
            # Keep segment as is
            result.append(seg)
            i += 1
        
        return result
