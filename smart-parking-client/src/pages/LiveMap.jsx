import { useState, useEffect } from 'react';
import api from '../services/api';
import HardwareSimulator from '../components/HardwareSimulator';

const ZONES = ['Zone A', 'Zone B', 'Zone C', 'Zone D'];

const CAR_IMAGE_URL =
  'https://cdn-icons-png.flaticon.com/512/3204/3204905.png';

export default function LiveMap() {
  const [parkingSlots, setParkingSlots] = useState([]);
  const [activeZone, setActiveZone] = useState('Zone A');

  useEffect(() => {
    const fetchSlots = async () => {
      try {
        const { data } = await api.get('/parking/map');
        setParkingSlots(data);
      } catch (err) {
        console.error('Failed to fetch parking map:', err);
      }
    };

    fetchSlots();
    const interval = setInterval(fetchSlots, 3000);
    return () => clearInterval(interval);
  }, []);

  /* ---------- derived stats ---------- */
  const totalSlots = parkingSlots.length;
  const occupiedCount = parkingSlots.filter((s) => s.isOccupied).length;
  const availableCount = totalSlots - occupiedCount;

  /* ---------- grid bounds ---------- */
  const maxCol = parkingSlots.reduce((m, s) => Math.max(m, s.gridX), 0);

  return (
    <div style={styles.page}>
      {/* --------- card wrapper --------- */}
      <div style={styles.card}>
        {/* ---- header row ---- */}
        <div style={styles.header}>
          <div>
            <h1 style={styles.title}>Parking Map</h1>
            <p style={styles.subtitle}>Real-time slot occupancy</p>
          </div>

          {/* stats badges */}
          <div style={styles.statsRow}>
            <span style={{ ...styles.badge, background: '#dcfce7', color: '#16a34a' }}>
              {availableCount} Available
            </span>
            <span style={{ ...styles.badge, background: '#fee2e2', color: '#dc2626' }}>
              {occupiedCount} Occupied
            </span>
          </div>
        </div>

        {/* ---- zone selector ---- */}
        <div style={styles.zoneRow}>
          {ZONES.map((zone) => (
            <button
              key={zone}
              onClick={() => setActiveZone(zone)}
              style={
                zone === activeZone ? styles.zonePillActive : styles.zonePill
              }
            >
              {zone}
            </button>
          ))}
        </div>

        {/* ---- legend ---- */}
        <div style={styles.legendRow}>
          <span style={styles.legendItem}>
            <span style={{ ...styles.legendDot, background: '#ffffff', border: '2px solid #e5e7eb' }} />
            Available
          </span>
          <span style={styles.legendItem}>
            <span style={{ ...styles.legendDot, background: '#fef3c7', border: '2px solid #eab308' }} />
            Occupied
          </span>
        </div>

        {/* ---- CSS grid map ---- */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${maxCol || 5}, 1fr)`,
            gap: '0px',
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            overflow: 'hidden',
          }}
        >
          {parkingSlots.map((slot) => (
            <div
              key={slot.slotId}
              style={{
                gridColumn: slot.gridX,
                gridRow: slot.gridY,
                minHeight: '140px',
                background: slot.isOccupied ? '#fef9e7' : '#ffffff',
                borderRight: '1px solid #e5e7eb',
                borderBottom: '1px solid #e5e7eb',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'background 0.3s ease',
                position: 'relative',
              }}
            >
              {slot.isOccupied ? (
                <img
                  src={CAR_IMAGE_URL}
                  alt="car"
                  style={{
                    width: '54px',
                    height: '54px',
                    filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.15))',
                    objectFit: 'contain',
                  }}
                />
              ) : (
                <span
                  style={{
                    fontSize: '18px',
                    fontWeight: 600,
                    color: '#9ca3af',
                    fontFamily: 'Inter, system-ui, sans-serif',
                  }}
                >
                  {slot.slotId}
                </span>
              )}

              {/* small label under car */}
              <span
                style={{
                  fontSize: '11px',
                  marginTop: '6px',
                  color: slot.isOccupied ? '#b45309' : '#d1d5db',
                  fontWeight: 500,
                }}
              >
                {slot.isOccupied ? 'Occupied' : 'Open'}
              </span>
            </div>
          ))}
        </div>

        {/* ---- developer tools ---- */}
        <div style={{ marginTop: '24px' }}>
          <HardwareSimulator />
        </div>
      </div>
    </div>
  );
}

/* =============== inline styles =============== */
const styles = {
  page: {
    minHeight: '100vh',
    background: '#f0f2f5',
    padding: '32px 16px',
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
  },
  card: {
    margin: '0 auto',
    maxWidth: '1400px',
    width: '100%',
    background: '#ffffff',
    borderRadius: '16px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06)',
    padding: '32px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    marginBottom: '24px',
    gap: '12px',
  },
  title: {
    fontSize: '22px',
    fontWeight: 700,
    color: '#111827',
    margin: 0,
  },
  subtitle: {
    fontSize: '14px',
    color: '#6b7280',
    margin: '4px 0 0',
  },
  statsRow: {
    display: 'flex',
    gap: '8px',
  },
  badge: {
    padding: '6px 14px',
    borderRadius: '20px',
    fontSize: '13px',
    fontWeight: 600,
  },
  zoneRow: {
    display: 'flex',
    gap: '8px',
    marginBottom: '20px',
    flexWrap: 'wrap',
  },
  zonePill: {
    padding: '8px 20px',
    borderRadius: '999px',
    border: '1px solid #d1d5db',
    background: '#ffffff',
    color: '#6b7280',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  zonePillActive: {
    padding: '8px 20px',
    borderRadius: '999px',
    border: '1px solid #eab308',
    background: '#eab308',
    color: '#ffffff',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  legendRow: {
    display: 'flex',
    gap: '20px',
    marginBottom: '16px',
    fontSize: '13px',
    color: '#6b7280',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  legendDot: {
    width: '14px',
    height: '14px',
    borderRadius: '4px',
    display: 'inline-block',
  },
};
