"""
Synthetic Data Generator for ML Model Training
===============================================

Generates realistic synthetic access patterns for training and testing
ML models without requiring real usage data.

Patterns Supported:
- Normal user behavior (predictable work patterns)
- Anomalous patterns (data exfiltration, brute force, unusual hours)
- Edge cases (burst access, long idle, device switches)

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @NEURAL @NEXUS
"""

import hashlib
import random
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Generator
from dataclasses import dataclass
from enum import Enum, auto
import secrets

from .access_logger import AccessEvent


class PatternType(Enum):
    """Types of synthetic access patterns."""
    NORMAL_WORKDAY = auto()      # Regular 9-5 work patterns
    NORMAL_EVENING = auto()      # Occasional evening access
    NORMAL_WEEKEND = auto()      # Light weekend usage
    
    ANOMALY_EXFILTRATION = auto()  # Mass file access (data theft)
    ANOMALY_BRUTE_FORCE = auto()   # Repeated failed attempts
    ANOMALY_ODD_HOURS = auto()     # 3 AM access patterns
    ANOMALY_NEW_DEVICE = auto()    # Unknown device access
    ANOMALY_BURST = auto()         # Sudden spike in activity
    ANOMALY_GEOGRAPHIC = auto()    # Access from unusual IPs
    
    EDGE_LONG_IDLE = auto()        # Return after extended absence
    EDGE_DEVICE_SWITCH = auto()    # Multiple device rapid switching


@dataclass
class UserProfile:
    """Simulated user profile for consistent behavior generation."""
    user_id: str
    primary_device: str
    typical_files: List[str]       # File paths this user typically accesses
    work_hours: Tuple[int, int]    # Start and end hour (e.g., (9, 17))
    avg_files_per_day: int
    avg_file_size: int
    error_rate: float              # Typical error rate
    ip_pool: List[str]             # Typical IP addresses


class SyntheticDataGenerator:
    """
    Generates synthetic access patterns for ML model training.
    
    This generator creates realistic access patterns that mimic:
    - Normal user behavior (workday patterns, file access sequences)
    - Anomalous patterns (data exfiltration, brute force attacks)
    - Edge cases (device switches, long idle periods)
    
    Example:
        >>> generator = SyntheticDataGenerator(seed=42)
        >>> normal_events = generator.generate_normal_workday(
        ...     vault_id="vault-123",
        ...     start_date=datetime(2025, 1, 1),
        ...     days=30
        ... )
        >>> len(normal_events)
        750  # ~25 events per day for 30 days
        
        >>> anomaly_events = generator.generate_anomaly(
        ...     pattern=PatternType.ANOMALY_EXFILTRATION,
        ...     vault_id="vault-123",
        ...     start_time=datetime(2025, 1, 15, 3, 0)  # 3 AM
        ... )
    """
    
    # Default file paths for simulation
    DEFAULT_FILES = [
        "/documents/report_q1.pdf",
        "/documents/report_q2.pdf",
        "/documents/budget_2025.xlsx",
        "/documents/presentation.pptx",
        "/code/main.py",
        "/code/utils.py",
        "/code/config.json",
        "/images/photo_001.jpg",
        "/images/photo_002.jpg",
        "/data/dataset.csv",
        "/data/analysis.ipynb",
        "/secrets/passwords.txt",
        "/secrets/api_keys.env",
        "/backup/archive.zip",
    ]
    
    # Default IP pools
    NORMAL_IPS = ["192.168.1.100", "192.168.1.101", "10.0.0.50"]
    ANOMALY_IPS = ["45.33.32.156", "185.220.101.1", "23.129.64.100"]  # Typical Tor/VPN
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize generator with optional seed for reproducibility.
        
        Args:
            seed: Random seed for reproducible generation
        """
        self.seed = seed or secrets.randbelow(2**32)
        self.rng = random.Random(self.seed)
        self.np_rng = np.random.Generator(np.random.PCG64(self.seed))
        
        # Default user profile
        self.default_profile = UserProfile(
            user_id="user-default",
            primary_device="desktop-main",
            typical_files=self.DEFAULT_FILES[:10],
            work_hours=(9, 17),
            avg_files_per_day=25,
            avg_file_size=50000,
            error_rate=0.02,
            ip_pool=self.NORMAL_IPS
        )
    
    def _hash_identifier(self, value: str) -> str:
        """Hash an identifier for privacy (consistent with AccessLogger)."""
        return hashlib.sha256(value.encode()).hexdigest()
    
    def _random_timestamp(
        self,
        base: datetime,
        hour_range: Tuple[int, int] = (9, 17),
        minute_spread: int = 60
    ) -> datetime:
        """Generate random timestamp within work hours."""
        hour = self.rng.randint(hour_range[0], hour_range[1] - 1)
        minute = self.rng.randint(0, 59)
        second = self.rng.randint(0, 59)
        microsecond = self.rng.randint(0, 999999)
        
        return base.replace(
            hour=hour,
            minute=minute,
            second=second,
            microsecond=microsecond
        )
    
    def _generate_event(
        self,
        timestamp: datetime,
        vault_id: str,
        file_path: str,
        operation: str,
        profile: UserProfile,
        success: bool = True,
        error_code: Optional[str] = None,
        device_override: Optional[str] = None,
        ip_override: Optional[str] = None
    ) -> AccessEvent:
        """Generate a single access event."""
        # Determine bytes based on operation
        if operation == "read":
            bytes_accessed = self.rng.gauss(profile.avg_file_size, profile.avg_file_size * 0.3)
        elif operation == "write":
            bytes_accessed = self.rng.gauss(profile.avg_file_size * 0.5, profile.avg_file_size * 0.2)
        elif operation == "stat":
            bytes_accessed = 0
        else:  # delete
            bytes_accessed = 0
        
        bytes_accessed = max(0, int(bytes_accessed))
        
        # Duration varies by operation and size
        base_duration = {
            "read": 5.0 + bytes_accessed / 100000,
            "write": 10.0 + bytes_accessed / 50000,
            "stat": 0.5,
            "delete": 2.0
        }[operation]
        duration_ms = max(0.1, self.rng.gauss(base_duration, base_duration * 0.2))
        
        return AccessEvent(
            timestamp=timestamp,
            vault_id=vault_id,
            file_path_hash=self._hash_identifier(file_path),
            operation=operation,
            bytes_accessed=bytes_accessed,
            duration_ms=round(duration_ms, 2),
            user_id_hash=self._hash_identifier(profile.user_id),
            device_fingerprint=device_override or profile.primary_device,
            ip_hash=self._hash_identifier(ip_override or self.rng.choice(profile.ip_pool)),
            success=success,
            error_code=error_code
        )
    
    def generate_normal_workday(
        self,
        vault_id: str,
        start_date: datetime,
        days: int = 30,
        profile: Optional[UserProfile] = None
    ) -> List[AccessEvent]:
        """
        Generate normal workday access patterns.
        
        Characteristics:
        - Access during work hours (9-17)
        - Regular file access patterns
        - Low error rate
        - Consistent device/IP
        
        Args:
            vault_id: Vault identifier
            start_date: Start date for generation
            days: Number of days to generate
            profile: Optional user profile
            
        Returns:
            List of AccessEvent objects
        """
        profile = profile or self.default_profile
        events = []
        
        for day in range(days):
            current_date = start_date + timedelta(days=day)
            
            # Skip weekends (80% chance)
            if current_date.weekday() >= 5 and self.rng.random() < 0.8:
                continue
            
            # Number of accesses today (normal distribution around average)
            daily_accesses = max(5, int(self.rng.gauss(
                profile.avg_files_per_day,
                profile.avg_files_per_day * 0.3
            )))
            
            # Generate accesses throughout the day
            for _ in range(daily_accesses):
                timestamp = self._random_timestamp(
                    current_date,
                    hour_range=profile.work_hours
                )
                
                file_path = self.rng.choice(profile.typical_files)
                operation = self.rng.choices(
                    ["read", "write", "stat"],
                    weights=[0.6, 0.25, 0.15]
                )[0]
                
                # Random error based on profile error rate
                success = self.rng.random() > profile.error_rate
                error_code = None if success else self.rng.choice([
                    "ENOENT", "EACCES", "EBUSY", "EIO"
                ])
                
                events.append(self._generate_event(
                    timestamp=timestamp,
                    vault_id=vault_id,
                    file_path=file_path,
                    operation=operation,
                    profile=profile,
                    success=success,
                    error_code=error_code
                ))
        
        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)
        return events
    
    def generate_anomaly(
        self,
        pattern: PatternType,
        vault_id: str,
        start_time: datetime,
        profile: Optional[UserProfile] = None,
        intensity: float = 1.0
    ) -> List[AccessEvent]:
        """
        Generate anomalous access patterns for detection testing.
        
        Args:
            pattern: Type of anomaly to generate
            vault_id: Vault identifier
            start_time: When the anomaly starts
            profile: User profile (may be ignored for some patterns)
            intensity: Anomaly intensity (0.5 = mild, 1.0 = normal, 2.0 = severe)
            
        Returns:
            List of AccessEvent objects representing the anomaly
        """
        profile = profile or self.default_profile
        
        generators = {
            PatternType.ANOMALY_EXFILTRATION: self._gen_exfiltration,
            PatternType.ANOMALY_BRUTE_FORCE: self._gen_brute_force,
            PatternType.ANOMALY_ODD_HOURS: self._gen_odd_hours,
            PatternType.ANOMALY_NEW_DEVICE: self._gen_new_device,
            PatternType.ANOMALY_BURST: self._gen_burst,
            PatternType.ANOMALY_GEOGRAPHIC: self._gen_geographic,
        }
        
        if pattern in generators:
            return generators[pattern](vault_id, start_time, profile, intensity)
        else:
            raise ValueError(f"Unknown anomaly pattern: {pattern}")
    
    def _gen_exfiltration(
        self,
        vault_id: str,
        start_time: datetime,
        profile: UserProfile,
        intensity: float
    ) -> List[AccessEvent]:
        """
        Generate data exfiltration pattern.
        
        Characteristics:
        - Mass file access in short time
        - Sequential file reads
        - Large bytes accessed
        - Unusual files accessed
        """
        events = []
        num_files = int(50 * intensity)
        
        # Access many files in rapid succession
        current_time = start_time
        all_files = self.DEFAULT_FILES + [
            f"/archive/backup_{i}.tar.gz" for i in range(20)
        ]
        
        for i in range(num_files):
            file_path = all_files[i % len(all_files)]
            
            events.append(self._generate_event(
                timestamp=current_time,
                vault_id=vault_id,
                file_path=file_path,
                operation="read",
                profile=profile,
                success=True
            ))
            
            # Very short intervals (exfiltration speed)
            current_time += timedelta(seconds=self.rng.uniform(0.5, 3.0))
        
        return events
    
    def _gen_brute_force(
        self,
        vault_id: str,
        start_time: datetime,
        profile: UserProfile,
        intensity: float
    ) -> List[AccessEvent]:
        """
        Generate brute force attack pattern.
        
        Characteristics:
        - Many failed access attempts
        - High error rate
        - Rapid attempts
        - Same files targeted repeatedly
        """
        events = []
        num_attempts = int(100 * intensity)
        target_files = ["/secrets/passwords.txt", "/secrets/api_keys.env"]
        
        current_time = start_time
        
        for _ in range(num_attempts):
            file_path = self.rng.choice(target_files)
            
            # 95% failure rate in brute force
            success = self.rng.random() > 0.95
            
            events.append(self._generate_event(
                timestamp=current_time,
                vault_id=vault_id,
                file_path=file_path,
                operation="read",
                profile=profile,
                success=success,
                error_code=None if success else "EACCES"
            ))
            
            # Very rapid attempts
            current_time += timedelta(milliseconds=self.rng.uniform(100, 500))
        
        return events
    
    def _gen_odd_hours(
        self,
        vault_id: str,
        start_time: datetime,
        profile: UserProfile,
        intensity: float
    ) -> List[AccessEvent]:
        """
        Generate odd hours access pattern.
        
        Characteristics:
        - Access at 2-5 AM
        - Otherwise normal behavior
        """
        events = []
        num_accesses = int(20 * intensity)
        
        # Force odd hours
        odd_start = start_time.replace(hour=3, minute=0)
        current_time = odd_start
        
        for _ in range(num_accesses):
            file_path = self.rng.choice(profile.typical_files)
            operation = self.rng.choices(
                ["read", "write", "stat"],
                weights=[0.6, 0.3, 0.1]
            )[0]
            
            events.append(self._generate_event(
                timestamp=current_time,
                vault_id=vault_id,
                file_path=file_path,
                operation=operation,
                profile=profile
            ))
            
            current_time += timedelta(minutes=self.rng.uniform(2, 15))
        
        return events
    
    def _gen_new_device(
        self,
        vault_id: str,
        start_time: datetime,
        profile: UserProfile,
        intensity: float
    ) -> List[AccessEvent]:
        """
        Generate new/unknown device access pattern.
        
        Characteristics:
        - Access from unknown device
        - Normal file access otherwise
        """
        events = []
        num_accesses = int(15 * intensity)
        new_device = f"unknown-device-{secrets.token_hex(4)}"
        
        current_time = start_time
        
        for _ in range(num_accesses):
            file_path = self.rng.choice(profile.typical_files)
            
            events.append(self._generate_event(
                timestamp=current_time,
                vault_id=vault_id,
                file_path=file_path,
                operation="read",
                profile=profile,
                device_override=new_device
            ))
            
            current_time += timedelta(minutes=self.rng.uniform(1, 10))
        
        return events
    
    def _gen_burst(
        self,
        vault_id: str,
        start_time: datetime,
        profile: UserProfile,
        intensity: float
    ) -> List[AccessEvent]:
        """
        Generate sudden burst of activity.
        
        Characteristics:
        - Many accesses in very short time
        - Normal files but extreme frequency
        """
        events = []
        num_accesses = int(200 * intensity)
        
        current_time = start_time
        
        for _ in range(num_accesses):
            file_path = self.rng.choice(profile.typical_files)
            operation = self.rng.choice(["read", "write", "stat"])
            
            events.append(self._generate_event(
                timestamp=current_time,
                vault_id=vault_id,
                file_path=file_path,
                operation=operation,
                profile=profile
            ))
            
            # Extremely short intervals
            current_time += timedelta(milliseconds=self.rng.uniform(50, 200))
        
        return events
    
    def _gen_geographic(
        self,
        vault_id: str,
        start_time: datetime,
        profile: UserProfile,
        intensity: float
    ) -> List[AccessEvent]:
        """
        Generate geographic anomaly (unusual IP addresses).
        
        Characteristics:
        - Access from unusual/suspicious IPs
        - Otherwise normal behavior
        """
        events = []
        num_accesses = int(25 * intensity)
        
        current_time = start_time
        
        for _ in range(num_accesses):
            file_path = self.rng.choice(profile.typical_files)
            suspicious_ip = self.rng.choice(self.ANOMALY_IPS)
            
            events.append(self._generate_event(
                timestamp=current_time,
                vault_id=vault_id,
                file_path=file_path,
                operation="read",
                profile=profile,
                ip_override=suspicious_ip
            ))
            
            current_time += timedelta(minutes=self.rng.uniform(5, 20))
        
        return events
    
    def generate_mixed_dataset(
        self,
        vault_id: str,
        start_date: datetime,
        days: int = 30,
        anomaly_days: Optional[List[int]] = None,
        anomaly_types: Optional[List[PatternType]] = None
    ) -> Tuple[List[AccessEvent], List[Tuple[int, int, PatternType]]]:
        """
        Generate a mixed dataset with both normal and anomalous patterns.
        
        Args:
            vault_id: Vault identifier
            start_date: Start date for generation
            days: Total days to generate
            anomaly_days: Days on which to inject anomalies (default: random 10%)
            anomaly_types: Types of anomalies to inject (default: random selection)
            
        Returns:
            Tuple of (events, anomaly_labels) where anomaly_labels is
            list of (start_idx, end_idx, pattern_type) tuples
        """
        # Generate normal baseline
        events = self.generate_normal_workday(vault_id, start_date, days)
        anomaly_labels = []
        
        # Default anomaly injection
        if anomaly_days is None:
            num_anomalies = max(1, days // 10)  # ~10% of days
            anomaly_days = sorted(self.rng.sample(range(days), num_anomalies))
        
        if anomaly_types is None:
            anomaly_types = [
                PatternType.ANOMALY_EXFILTRATION,
                PatternType.ANOMALY_BRUTE_FORCE,
                PatternType.ANOMALY_ODD_HOURS,
                PatternType.ANOMALY_BURST,
            ]
        
        # Inject anomalies
        for day_offset in anomaly_days:
            anomaly_date = start_date + timedelta(days=day_offset)
            pattern = self.rng.choice(anomaly_types)
            
            # Random time during that day
            hour = self.rng.randint(0, 23)
            anomaly_time = anomaly_date.replace(hour=hour, minute=0)
            
            # Generate anomaly events
            anomaly_events = self.generate_anomaly(
                pattern=pattern,
                vault_id=vault_id,
                start_time=anomaly_time,
                intensity=self.rng.uniform(0.8, 1.5)
            )
            
            if anomaly_events:
                start_idx = len(events)
                events.extend(anomaly_events)
                end_idx = len(events)
                anomaly_labels.append((start_idx, end_idx, pattern))
        
        # Sort all events by timestamp
        events.sort(key=lambda e: e.timestamp)
        
        return events, anomaly_labels
    
    def generate_training_batch(
        self,
        vault_id: str,
        normal_count: int = 1000,
        anomaly_count: int = 100,
        start_date: Optional[datetime] = None
    ) -> Tuple[List[List[AccessEvent]], List[bool]]:
        """
        Generate labeled training data for ML models.
        
        Returns sequences of events labeled as normal or anomalous.
        
        Args:
            vault_id: Vault identifier
            normal_count: Number of normal sequences
            anomaly_count: Number of anomaly sequences
            start_date: Start date (default: now - 90 days)
            
        Returns:
            Tuple of (sequences, labels) where labels[i] is True for anomaly
        """
        start_date = start_date or datetime.now() - timedelta(days=90)
        sequences = []
        labels = []
        
        # Generate normal sequences (1 hour windows)
        normal_events = self.generate_normal_workday(
            vault_id, start_date, days=max(60, normal_count // 10)
        )
        
        # Window into sequences
        window_size = timedelta(hours=1)
        current_window = []
        window_start = None
        
        for event in normal_events:
            if window_start is None:
                window_start = event.timestamp
                current_window = [event]
            elif event.timestamp - window_start < window_size:
                current_window.append(event)
            else:
                if len(current_window) >= 3:  # Min events per window
                    sequences.append(current_window)
                    labels.append(False)  # Normal
                window_start = event.timestamp
                current_window = [event]
            
            if len(sequences) >= normal_count:
                break
        
        # Generate anomaly sequences
        anomaly_patterns = list(PatternType)
        anomaly_patterns = [p for p in anomaly_patterns if 'ANOMALY' in p.name]
        
        for i in range(anomaly_count):
            pattern = self.rng.choice(anomaly_patterns)
            anomaly_time = start_date + timedelta(days=self.rng.randint(0, 60))
            
            anomaly_events = self.generate_anomaly(
                pattern=pattern,
                vault_id=vault_id,
                start_time=anomaly_time
            )
            
            if len(anomaly_events) >= 3:
                sequences.append(anomaly_events)
                labels.append(True)  # Anomaly
        
        return sequences, labels


def generate_test_data(seed: int = 42) -> Tuple[List[AccessEvent], List[AccessEvent]]:
    """
    Convenience function to generate test data for ML testing.
    
    Returns:
        Tuple of (normal_events, anomaly_events)
    """
    generator = SyntheticDataGenerator(seed=seed)
    
    # Normal events (30 days of workday activity)
    normal_events = generator.generate_normal_workday(
        vault_id="test-vault",
        start_date=datetime(2025, 1, 1),
        days=30
    )
    
    # Anomaly events (mixed patterns)
    anomaly_events = []
    for pattern in [
        PatternType.ANOMALY_EXFILTRATION,
        PatternType.ANOMALY_BRUTE_FORCE,
        PatternType.ANOMALY_BURST
    ]:
        events = generator.generate_anomaly(
            pattern=pattern,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15, 3, 0)
        )
        anomaly_events.extend(events)
    
    return normal_events, anomaly_events
