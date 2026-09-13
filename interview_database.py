#!/usr/bin/env python3

"""
Interview History Database for interview-notify-advanced
Tracks interview statistics and outcomes for analysis
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import logging
from contextlib import contextmanager


class InterviewDatabase:
    def __init__(self, db_path=None):
        """Initialize database connection"""
        if db_path is None:
            db_path = Path.home() / '.interview-notify-history.db'
        else:
            db_path = Path(db_path)

        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        # Enable WAL mode for better concurrent access and set timeout
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            conn.row_factory = sqlite3.Row

            # Enable Write-Ahead Logging for better concurrency
            conn.execute('PRAGMA journal_mode=WAL')

            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_database(self):
        """Create database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Interviews table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    queue_length INTEGER,
                    channel TEXT,
                    outcome_message TEXT
                )
            ''')

            # Queue snapshots table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS queue_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    queue_length INTEGER NOT NULL,
                    channel TEXT
                )
            ''')

            # Indexes for better query performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interviews_timestamp
                ON interviews(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interviews_username
                ON interviews(username)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interviews_event_type
                ON interviews(event_type)
            ''')

            logging.debug(f"Database initialized at {self.db_path}")

    def record_interview_start(self, username, queue_length=None, channel=None):
        """Record when an interview starts"""
        # Validate inputs
        if not username or not isinstance(username, str):
            logging.warning(f"Invalid username: {username}")
            return

        if queue_length is not None and (not isinstance(queue_length, int) or queue_length < 0):
            logging.warning(f"Invalid queue_length: {queue_length}")
            queue_length = None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interviews (username, timestamp, event_type, queue_length, channel)
                VALUES (?, ?, ?, ?, ?)
            ''', (username[:100], datetime.now().isoformat(), 'started', queue_length, channel[:100] if channel else None))

            logging.debug(f"Recorded interview start for {username}")

    def record_interview_outcome(self, username, outcome, message=None, channel=None):
        """Record interview outcome (passed, failed, missed)"""
        # Validate inputs
        if not username or not isinstance(username, str):
            logging.warning(f"Invalid username: {username}")
            return

        if outcome not in ['passed', 'failed', 'missed']:
            logging.warning(f"Invalid outcome: {outcome}")
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interviews (username, timestamp, event_type, channel, outcome_message)
                VALUES (?, ?, ?, ?, ?)
            ''', (username[:100], datetime.now().isoformat(), outcome, channel[:100] if channel else None, message[:500] if message else None))

            logging.debug(f"Recorded interview outcome for {username}: {outcome}")

    def record_queue_snapshot(self, queue_length, channel=None):
        """Record current queue length"""
        # Validate input
        if not isinstance(queue_length, int) or queue_length < 0:
            logging.warning(f"Invalid queue_length for snapshot: {queue_length}")
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO queue_snapshots (timestamp, queue_length, channel)
                VALUES (?, ?, ?)
            ''', (datetime.now().isoformat(), queue_length, channel[:100] if channel else None))

    def get_statistics(self, days=30, channel=None):
        """Get interview statistics for the past N days"""
        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build channel filter
            channel_filter = "AND channel = ?" if channel else ""
            params = [start_date, channel] if channel else [start_date]

            # Total interviews
            cursor.execute(f'''
                SELECT COUNT(*) as total
                FROM interviews
                WHERE event_type = 'started'
                AND timestamp >= ?
                {channel_filter}
            ''', params)
            total_interviews = cursor.fetchone()['total']

            # Outcomes
            cursor.execute(f'''
                SELECT event_type, COUNT(*) as count
                FROM interviews
                WHERE event_type IN ('passed', 'failed', 'missed')
                AND timestamp >= ?
                {channel_filter}
                GROUP BY event_type
            ''', params)
            outcomes = {row['event_type']: row['count'] for row in cursor.fetchall()}

            # Average queue length
            cursor.execute(f'''
                SELECT AVG(queue_length) as avg_queue
                FROM interviews
                WHERE queue_length IS NOT NULL
                AND timestamp >= ?
                {channel_filter}
            ''', params)
            avg_queue = cursor.fetchone()['avg_queue'] or 0

            # Busiest hours
            cursor.execute(f'''
                SELECT
                    CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                    COUNT(*) as count
                FROM interviews
                WHERE event_type = 'started'
                AND timestamp >= ?
                {channel_filter}
                GROUP BY hour
                ORDER BY count DESC
                LIMIT 5
            ''', params)
            busiest_hours = [(row['hour'], row['count']) for row in cursor.fetchall()]

            return {
                'total_interviews': total_interviews,
                'passed': outcomes.get('passed', 0),
                'failed': outcomes.get('failed', 0),
                'missed': outcomes.get('missed', 0),
                'avg_queue_length': round(avg_queue, 1),
                'busiest_hours': busiest_hours,
                'pass_rate': round((outcomes.get('passed', 0) / max(sum(outcomes.values()), 1)) * 100, 1)
            }

    def get_recent_interviews(self, limit=20, channel=None):
        """Get recent interview events"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            channel_filter = "WHERE channel = ?" if channel else ""
            params = [channel, limit] if channel else [limit]

            cursor.execute(f'''
                SELECT username, timestamp, event_type, queue_length, outcome_message
                FROM interviews
                {channel_filter}
                ORDER BY timestamp DESC
                LIMIT ?
            ''', params)

            return [dict(row) for row in cursor.fetchall()]

    def get_user_history(self, username, limit=10):
        """Get interview history for a specific user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT timestamp, event_type, outcome_message
                FROM interviews
                WHERE username = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (username, limit))

            return [dict(row) for row in cursor.fetchall()]

    def get_queue_trends(self, hours=24, channel=None):
        """Get queue length trends over time"""
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            channel_filter = "AND channel = ?" if channel else ""
            params = [start_time, channel] if channel else [start_time]

            cursor.execute(f'''
                SELECT timestamp, queue_length
                FROM queue_snapshots
                WHERE timestamp >= ?
                {channel_filter}
                ORDER BY timestamp ASC
            ''', params)

            return [(row['timestamp'], row['queue_length']) for row in cursor.fetchall()]

    def clear_old_data(self, days=90):
        """Clear data older than N days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('DELETE FROM interviews WHERE timestamp < ?', (cutoff_date,))
            deleted_interviews = cursor.rowcount

            cursor.execute('DELETE FROM queue_snapshots WHERE timestamp < ?', (cutoff_date,))
            deleted_snapshots = cursor.rowcount

            total_deleted = deleted_interviews + deleted_snapshots
            logging.info(f"Cleared {total_deleted} old database records ({deleted_interviews} interviews, {deleted_snapshots} snapshots)")
            return total_deleted
