"""
Feature Extractor for ML Models
================================

Extracts statistical features from access event logs for ML training.

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @NEURAL
"""

import numpy as np
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .access_logger import AccessEvent


class FeatureExtractor:
    """
    Extract ML features from access event sequences.
    
    Features extracted:
    - access_frequency: Events per hour
    - unique_files: Number of distinct files accessed
    - read_write_ratio: Read operations / (Read + Write)
    - avg_file_size: Mean bytes accessed per operation
    - access_entropy: Shannon entropy of access intervals
    - time_of_day_mean: Average hour of access (0-23)
    - time_of_day_std: Standard deviation of access hours
    - session_duration: Duration from first to last event (minutes)
    - error_rate: Failed operations / Total operations
    - ip_diversity: Unique IP hashes / Total accesses
    - operation_diversity: Entropy of operation types
    
    Example:
        >>> extractor = FeatureExtractor()
        >>> events = logger.get_recent_events(window=timedelta(hours=1))
        >>> features = extractor.extract(events)
        >>> print(features['access_frequency'])
        24.5
    """
    
    def extract(
        self,
        events: List[AccessEvent],
        window: Optional[timedelta] = None
    ) -> Dict[str, float]:
        """
        Extract features from event sequence.
        
        Args:
            events: List of AccessEvent objects
            window: Optional time window for frequency calculations
            
        Returns:
            Dictionary of feature name -> value
        """
        if not events:
            return self._empty_features()
        
        # Sort by timestamp
        events = sorted(events, key=lambda e: e.timestamp)
        
        # Calculate time-based features
        first_time = events[0].timestamp
        last_time = events[-1].timestamp
        session_duration = (last_time - first_time).total_seconds() / 60  # minutes
        
        if window is None:
            window = last_time - first_time
            if window.total_seconds() == 0:
                window = timedelta(seconds=1)
        
        window_hours = window.total_seconds() / 3600
        
        # Extract basic counts
        total_events = len(events)
        successful_events = sum(1 for e in events if e.success)
        failed_events = total_events - successful_events
        
        # File access patterns
        file_hashes = [e.file_path_hash for e in events]
        unique_files = len(set(file_hashes))
        
        # Operation patterns
        operations = [e.operation for e in events]
        operation_counts = Counter(operations)
        reads = operation_counts.get('read', 0)
        writes = operation_counts.get('write', 0)
        
        # Read/write ratio (avoid division by zero)
        read_write_ratio = reads / max(1, reads + writes)
        
        # File sizes
        sizes = [e.bytes_accessed for e in events if e.bytes_accessed > 0]
        avg_file_size = np.mean(sizes) if sizes else 0.0
        
        # Time of day patterns (hour of day)
        hours = [e.timestamp.hour for e in events]
        time_of_day_mean = np.mean(hours)
        time_of_day_std = np.std(hours) if len(hours) > 1 else 0.0
        
        # Access entropy (Shannon entropy of inter-access intervals)
        access_entropy = self._calculate_access_entropy(events)
        
        # IP diversity
        ip_hashes = [e.ip_hash for e in events if e.ip_hash]
        unique_ips = len(set(ip_hashes))
        ip_diversity = unique_ips / total_events if total_events > 0 else 0.0
        
        # Operation diversity (Shannon entropy of operation types)
        operation_diversity = self._calculate_operation_entropy(operations)
        
        # Error rate
        error_rate = failed_events / total_events if total_events > 0 else 0.0
        
        # Access frequency (events per hour)
        access_frequency = total_events / max(0.01, window_hours)
        
        return {
            'access_frequency': access_frequency,
            'unique_files': float(unique_files),
            'read_write_ratio': read_write_ratio,
            'avg_file_size': avg_file_size,
            'access_entropy': access_entropy,
            'time_of_day_mean': time_of_day_mean,
            'time_of_day_std': time_of_day_std,
            'session_duration': session_duration,
            'error_rate': error_rate,
            'ip_diversity': ip_diversity,
            'operation_diversity': operation_diversity,
        }
    
    def _calculate_access_entropy(self, events: List[AccessEvent]) -> float:
        """
        Calculate Shannon entropy of inter-access intervals.
        
        Higher entropy = more random access pattern
        Lower entropy = more regular/predictable pattern
        
        Args:
            events: Sorted list of AccessEvent objects
            
        Returns:
            Shannon entropy (bits)
        """
        if len(events) < 2:
            return 0.0
        
        # Calculate inter-access intervals (seconds)
        intervals = []
        for i in range(1, len(events)):
            delta = (events[i].timestamp - events[i-1].timestamp).total_seconds()
            intervals.append(delta)
        
        if not intervals:
            return 0.0
        
        # Bin intervals into buckets (logarithmic scale)
        bins = [0, 1, 5, 10, 30, 60, 300, 900, 3600, float('inf')]
        binned = np.digitize(intervals, bins)
        
        # Calculate entropy
        counts = Counter(binned)
        total = len(intervals)
        
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        
        return entropy
    
    def _calculate_operation_entropy(self, operations: List[str]) -> float:
        """
        Calculate Shannon entropy of operation types.
        
        Args:
            operations: List of operation strings
            
        Returns:
            Shannon entropy (bits)
        """
        if not operations:
            return 0.0
        
        counts = Counter(operations)
        total = len(operations)
        
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        
        return entropy
    
    def _empty_features(self) -> Dict[str, float]:
        """Return zero-valued features for empty event list."""
        return {
            'access_frequency': 0.0,
            'unique_files': 0.0,
            'read_write_ratio': 0.0,
            'avg_file_size': 0.0,
            'access_entropy': 0.0,
            'time_of_day_mean': 0.0,
            'time_of_day_std': 0.0,
            'session_duration': 0.0,
            'error_rate': 0.0,
            'ip_diversity': 0.0,
            'operation_diversity': 0.0,
        }
    
    def extract_batch(
        self,
        event_sequences: List[List[AccessEvent]],
        window: Optional[timedelta] = None
    ) -> np.ndarray:
        """
        Extract features from multiple event sequences (for batch training).
        
        Args:
            event_sequences: List of event lists
            window: Optional time window for frequency calculations
            
        Returns:
            2D numpy array of shape (n_sequences, n_features)
        """
        feature_dicts = [self.extract(events, window) for events in event_sequences]
        
        if not feature_dicts:
            return np.array([])
        
        # Convert to 2D array
        feature_names = sorted(feature_dicts[0].keys())
        feature_matrix = np.array([
            [fd[name] for name in feature_names]
            for fd in feature_dicts
        ])
        
        return feature_matrix
    
    def get_feature_names(self) -> List[str]:
        """Get ordered list of feature names."""
        return sorted([
            'access_frequency',
            'unique_files',
            'read_write_ratio',
            'avg_file_size',
            'access_entropy',
            'time_of_day_mean',
            'time_of_day_std',
            'session_duration',
            'error_rate',
            'ip_diversity',
            'operation_diversity',
        ])
