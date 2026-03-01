import { useState } from 'react';
import api from '../services/api';

export default function ApplyReceiptPage() {
  const [receiptUid, setReceiptUid] = useState('');
  const [message, setMessage] = useState(null);
  const [isError, setIsError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleApplyReceipt = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage(null);

    try {
      const { data } = await api.post('/parking/apply-receipt', { receiptUid });
      setIsError(false);
      setReceiptUid('');
      setMessage(data.message || `Success! ${Number(data.discountAmount).toLocaleString()} credits discount applied.`);
    } catch (err) {
      setIsError(true);
      setMessage(err.response?.data?.message || 'Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.iconCircle}>🧾</div>
        <h1 style={styles.title}>Claim Parking Discount</h1>
        <p style={styles.subtitle}>
          Enter the code from your supermarket receipt to apply a discount to your current parking session.
        </p>

        <form onSubmit={handleApplyReceipt} style={styles.form}>
          <input
            type="text"
            value={receiptUid}
            onChange={(e) => setReceiptUid(e.target.value)}
            placeholder="e.g. RCP-20260228-001"
            required
            style={styles.input}
          />
          <button
            type="submit"
            disabled={isLoading}
            style={{
              ...styles.button,
              ...(isLoading ? styles.buttonDisabled : {}),
            }}
          >
            {isLoading ? 'Submitting...' : 'Submit'}
          </button>
        </form>

        {message && (
          <div
            style={{
              ...styles.messageBox,
              ...(isError ? styles.messageError : styles.messageSuccess),
            }}
          >
            {isError ? '❌' : '✅'} {message}
          </div>
        )}
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
  card: {
    width: '100%',
    maxWidth: '460px',
    background: '#ffffff',
    borderRadius: '16px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06)',
    padding: '40px 32px',
    height: 'fit-content',
    textAlign: 'center',
  },
  iconCircle: {
    fontSize: '48px',
    marginBottom: '12px',
  },
  title: {
    fontSize: '22px',
    fontWeight: 700,
    color: '#111827',
    margin: '0 0 8px',
  },
  subtitle: {
    fontSize: '14px',
    color: '#6b7280',
    lineHeight: '1.5',
    margin: '0 0 28px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  input: {
    width: '100%',
    padding: '12px 16px',
    borderRadius: '10px',
    border: '1px solid #d1d5db',
    fontSize: '15px',
    fontFamily: 'monospace',
    letterSpacing: '0.5px',
    outline: 'none',
    transition: 'border 0.2s',
    boxSizing: 'border-box',
  },
  button: {
    padding: '12px',
    borderRadius: '10px',
    border: 'none',
    background: '#111827',
    color: '#ffffff',
    fontSize: '15px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background 0.2s',
    fontFamily: 'inherit',
  },
  buttonDisabled: {
    background: '#9ca3af',
    cursor: 'not-allowed',
  },
  messageBox: {
    marginTop: '20px',
    padding: '14px 16px',
    borderRadius: '10px',
    fontSize: '14px',
    fontWeight: 600,
    textAlign: 'center',
  },
  messageSuccess: {
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    color: '#15803d',
  },
  messageError: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    color: '#dc2626',
  },
};
