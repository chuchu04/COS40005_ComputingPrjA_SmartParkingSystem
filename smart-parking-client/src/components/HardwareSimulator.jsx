import { useState } from 'react';
import api from '../services/api';

export default function HardwareSimulator() {
  const [simulationMessage, setSimulationMessage] = useState('');
  const [loadingEntry, setLoadingEntry] = useState(false);
  const [loadingExit, setLoadingExit] = useState(false);

  const handleSimulateEntry = async () => {
    setLoadingEntry(true);
    setSimulationMessage('');

    try {
      const { data } = await api.post('/parking/simulate-entry');
      setSimulationMessage(
        `Success! Car ${data.licensePlate} parked in ${data.slotId}`
      );
    } catch (err) {
      const msg =
        err.response?.data?.message || 'Simulation failed. Please try again.';
      setSimulationMessage(msg);
    } finally {
      setLoadingEntry(false);
    }
  };

  const handleSimulateExit = async () => {
    setLoadingExit(true);
    setSimulationMessage('');

    try {
      const { data } = await api.post('/parking/simulate-exit');
      setSimulationMessage(`Exit successful. Gate opened and ${Number(data.fee).toLocaleString()} credits deducted.`);
    } catch (err) {
      const msg = err.response?.data?.message || 'Exit failed. Please try again.';
      if (msg.toLowerCase().includes('insufficient')) {
        setSimulationMessage('❌ Exit Denied: Insufficient wallet balance. Please top up your account.');
      } else {
        setSimulationMessage(msg);
      }
    } finally {
      setLoadingExit(false);
    }
  };

  const isError =
    simulationMessage &&
    (/denied|insufficient|fail|full|no active/i.test(simulationMessage));

  return (
    <div style={styles.card}>
      <div style={styles.buttonRow}>
        <button
          onClick={handleSimulateEntry}
          disabled={loadingEntry || loadingExit}
          style={styles.button}
        >
          {loadingEntry ? 'Creating...' : 'Create Parking Session'}
        </button>
        <button
          onClick={handleSimulateExit}
          disabled={loadingEntry || loadingExit}
          style={styles.exitButton}
        >
          {loadingExit ? 'Processing...' : 'Exit'}
        </button>
      </div>

      {simulationMessage && (
        <p style={isError ? styles.msgError : styles.msgSuccess}>
          {simulationMessage}
        </p>
      )}
    </div>
  );
}

const styles = {
  card: {
    background: '#ffffff',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
    padding: '24px',
    maxWidth: '520px',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  buttonRow: {
    display: 'flex',
    gap: '10px',
  },
  button: {
    flex: 1,
    padding: '10px 20px',
    borderRadius: '8px',
    border: 'none',
    background: '#111827',
    color: '#ffffff',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
    transition: 'background 0.2s',
  },
  exitButton: {
    flex: 1,
    padding: '10px 20px',
    borderRadius: '8px',
    border: '1px solid #dc2626',
    background: '#ffffff',
    color: '#dc2626',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
    transition: 'all 0.2s',
  },
  msgSuccess: {
    marginTop: '16px',
    padding: '10px 14px',
    borderRadius: '8px',
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    color: '#15803d',
    fontSize: '13px',
    fontWeight: 500,
  },
  msgError: {
    marginTop: '16px',
    padding: '10px 14px',
    borderRadius: '8px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    color: '#dc2626',
    fontSize: '13px',
    fontWeight: 500,
  },
};
