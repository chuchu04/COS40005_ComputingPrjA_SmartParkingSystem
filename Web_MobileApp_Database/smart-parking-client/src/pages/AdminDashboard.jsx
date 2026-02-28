import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/api';
import api from '../services/api';

const formatVND = (amount) =>
  new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);

export default function ProfilePage({ onLogout }) {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [walletBalance, setWalletBalance] = useState(0);
  const [activeSession, setActiveSession] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [profileRes, sessionRes] = await Promise.allSettled([
          authService.getProfile(),
          api.get('/parking/active-session'),
        ]);

        if (profileRes.status === 'fulfilled') {
          setProfile(profileRes.value);
          setWalletBalance(profileRes.value.walletBalance ?? 0);
        } else {
          setError('Failed to load profile.');
        }

        if (sessionRes.status === 'fulfilled') {
          const status = sessionRes.value.status;
          if (status === 200) {
            setActiveSession(sessionRes.value.data);
          }
          // 204 or other → leave null
        }
        // 404 from rejected promise → leave null
      } catch {
        setError('Failed to load data.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleLogout = () => {
    authService.logout();
    onLogout();
    navigate('/login');
  };

  if (isLoading) {
    return (
      <div style={styles.page}>
        <div style={styles.container}>
          <div style={styles.card}>
            <p style={{ color: '#6b7280', textAlign: 'center' }}>Loading dashboard...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.page}>
        <div style={styles.container}>
          <div style={styles.card}>
            <p style={{ color: '#dc2626', textAlign: 'center' }}>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        {/* ─── Profile Header ─── */}
        <div style={styles.card}>
          <div style={styles.header}>
            <div style={styles.avatar}>
              {profile.userName?.charAt(0).toUpperCase()}
            </div>
            <div>
              <h1 style={styles.name}>{profile.userName}</h1>
              <p style={styles.email}>{profile.email}</p>
            </div>
          </div>
          <button onClick={handleLogout} style={styles.logoutBtn}>
            Sign Out
          </button>
        </div>

        {/* ─── Card 1: Digital Wallet ─── */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>
            <span style={styles.cardIcon}>💳</span> Digital Wallet
          </div>
          <div style={styles.walletCard}>
            <div style={styles.walletLabel}>Available Balance</div>
            <div style={styles.walletAmount}>{formatVND(walletBalance)}</div>
          </div>
        </div>

        {/* ─── Card 2: Current Parking Session ─── */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>
            <span style={styles.cardIcon}>🚗</span> Current Parking Session
          </div>

          {activeSession === null ? (
            <div style={styles.emptySession}>
              <div style={styles.emptyIcon}>🅿️</div>
              <p style={styles.emptyText}>
                You currently have no active parking sessions.
              </p>
            </div>
          ) : (
            <div style={styles.sessionContent}>
              {/* License Plate */}
              <div style={styles.plateContainer}>
                <div style={styles.plateBadge}>{activeSession.licensePlate}</div>
              </div>

              {/* Session details */}
              <div style={styles.sessionDetails}>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>Entry Time</span>
                  <span style={styles.detailValue}>
                    {new Date(activeSession.entryTime).toLocaleString('vi-VN', {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })}
                  </span>
                </div>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>Duration</span>
                  <span style={styles.detailValue}>
                    {activeSession.durationHours < 1
                      ? `${Math.round(activeSession.durationHours * 60)} minutes`
                      : `${activeSession.durationHours} hours`}
                  </span>
                </div>
              </div>

              {/* Accrued Fee */}
              <div style={styles.feeCard}>
                <div style={styles.feeLabel}>Base Fee</div>
                <div style={styles.feeAmount}>{formatVND(activeSession.currentFee)}</div>
              </div>

              {/* Discount row */}
              {activeSession.discount > 0 && (
                <div style={styles.discountCard}>
                  <div style={styles.discountLabel}>🧾 Receipt Discount</div>
                  <div style={styles.discountAmount}>-{formatVND(activeSession.discount)}</div>
                </div>
              )}

              {/* Final Fee */}
              {activeSession.discount > 0 && (
                <div style={styles.feeCard}>
                  <div style={styles.feeLabel}>Final Fee</div>
                  <div style={{...styles.feeAmount, color: '#059669'}}>{formatVND(activeSession.finalFee)}</div>
                </div>
              )}

              {/* Insufficient balance warning */}
              {walletBalance < (activeSession.finalFee ?? activeSession.currentFee) && (
                <div style={styles.warningBadge}>
                  ⚠️ Insufficient balance for exit. Please top up!
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: 'calc(100vh - 56px)',
    background: '#f0f2f5',
    padding: '32px 16px',
    display: 'flex',
    justifyContent: 'center',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  container: {
    width: '100%',
    maxWidth: '520px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  card: {
    background: '#ffffff',
    borderRadius: '16px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06)',
    padding: '28px 28px',
  },
  cardTitle: {
    fontSize: '16px',
    fontWeight: 700,
    color: '#111827',
    marginBottom: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  cardIcon: {
    fontSize: '20px',
  },
  /* ── Profile Header ── */
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginBottom: '20px',
  },
  avatar: {
    width: '56px',
    height: '56px',
    borderRadius: '50%',
    background: '#111827',
    color: '#ffffff',
    fontSize: '22px',
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  name: {
    fontSize: '20px',
    fontWeight: 700,
    color: '#111827',
    margin: '0 0 2px',
  },
  email: {
    fontSize: '14px',
    color: '#6b7280',
    margin: 0,
  },
  /* ── Wallet ── */
  walletCard: {
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: '12px',
    padding: '24px',
    textAlign: 'center',
  },
  walletLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#16a34a',
    textTransform: 'uppercase',
    letterSpacing: '0.8px',
    marginBottom: '6px',
  },
  walletAmount: {
    fontSize: '32px',
    fontWeight: 700,
    color: '#15803d',
  },
  /* ── Empty Session ── */
  emptySession: {
    textAlign: 'center',
    padding: '24px 0',
  },
  emptyIcon: {
    fontSize: '48px',
    marginBottom: '12px',
  },
  emptyText: {
    fontSize: '15px',
    color: '#6b7280',
    margin: 0,
  },
  /* ── Active Session ── */
  sessionContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  plateContainer: {
    textAlign: 'center',
  },
  plateBadge: {
    display: 'inline-block',
    background: '#fef9c3',
    border: '2px solid #facc15',
    borderRadius: '8px',
    padding: '8px 24px',
    fontSize: '20px',
    fontWeight: 800,
    fontFamily: 'monospace',
    color: '#1c1917',
    letterSpacing: '2px',
  },
  sessionDetails: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    background: '#f9fafb',
    borderRadius: '10px',
    padding: '16px',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  detailLabel: {
    fontSize: '13px',
    fontWeight: 500,
    color: '#6b7280',
  },
  detailValue: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#111827',
  },
  /* ── Fee ── */
  feeCard: {
    background: '#eff6ff',
    border: '1px solid #bfdbfe',
    borderRadius: '12px',
    padding: '20px',
    textAlign: 'center',
  },
  feeLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#2563eb',
    textTransform: 'uppercase',
    letterSpacing: '0.8px',
    marginBottom: '6px',
  },
  feeAmount: {
    fontSize: '28px',
    fontWeight: 700,
    color: '#1d4ed8',
  },
  /* ── Discount ── */
  discountCard: {
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: '12px',
    padding: '14px 20px',
    textAlign: 'center',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  discountLabel: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#059669',
  },
  discountAmount: {
    fontSize: '18px',
    fontWeight: 700,
    color: '#059669',
  },
  /* ── Warning ── */
  warningBadge: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '10px',
    padding: '12px 16px',
    fontSize: '14px',
    fontWeight: 600,
    color: '#dc2626',
    textAlign: 'center',
  },
  /* ── Logout ── */
  logoutBtn: {
    width: '100%',
    padding: '10px',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    background: '#ffffff',
    color: '#dc2626',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background 0.2s',
    fontFamily: 'inherit',
  },
};
