import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { authService, walletService } from '../services/api';

const formatVnd = (value) =>
  new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(value ?? 0);

const getTransactionTypeLabel = (type) => {
  const key = String(type).toLowerCase();

  if (key === '0' || key === 'topup') {
    return 'Fund Added';
  }

  if (key === '1' || key === 'parkingfee') {
    return 'Payment Made';
  }

  return 'Transaction';
};

const getTransactionStatusLabel = (status) => {
  const key = String(status).toLowerCase();

  if (key === '0' || key === 'pending') {
    return 'Pending';
  }

  if (key === '1' || key === 'completed') {
    return 'Completed';
  }

  if (key === '2' || key === 'failed') {
    return 'Failed';
  }

  return 'Unknown';
};

const TRANSACTIONS_PER_PAGE = 5;

export default function WalletDashboard() {
  const [searchParams] = useSearchParams();
  const [profile, setProfile] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [amount, setAmount] = useState('100000');
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const callbackState = useMemo(() => {
    const topup = searchParams.get('topup');
    const reason = searchParams.get('reason');
    const orderCode = searchParams.get('orderCode');
    return { topup, reason, orderCode };
  }, [searchParams]);

  const loadData = async () => {
    setLoading(true);
    setError('');

    try {
      const [profileData, txData] = await Promise.all([
        authService.getProfile(),
        walletService.getTransactions(),
      ]);

      setProfile(profileData);
      setTransactions(txData);
      setCurrentPage(1);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load wallet data.');
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(transactions.length / TRANSACTIONS_PER_PAGE));

  const pagedTransactions = useMemo(() => {
    const startIndex = (currentPage - 1) * TRANSACTIONS_PER_PAGE;
    const endIndex = startIndex + TRANSACTIONS_PER_PAGE;
    return transactions.slice(startIndex, endIndex);
  }, [transactions, currentPage]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (callbackState.topup === 'success') {
      setMessage(`Top-up successful${callbackState.orderCode ? ` (Order ${callbackState.orderCode})` : ''}.`);
      setError('');
      loadData();
    }

    if (callbackState.topup === 'failed') {
      setError(`Top-up failed${callbackState.reason ? ` (${callbackState.reason})` : ''}.`);
      setMessage('');
      loadData();
    }
  }, [callbackState.topup, callbackState.reason, callbackState.orderCode]);

  const handleTopUp = async (e) => {
    e.preventDefault();
    setMessage('');
    setError('');

    const parsedAmount = Number(amount);
    if (!Number.isFinite(parsedAmount) || parsedAmount < 10000) {
      setError('Minimum top-up amount is 10,000 VND.');
      return;
    }

    setSubmitting(true);
    try {
      const data = await walletService.createTopUpPaymentUrl(parsedAmount);
      window.location.href = data.paymentUrl;
    } catch (err) {
      setError(err.response?.data?.message || 'Unable to create VNPay payment URL.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>Loading wallet...</div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <div style={styles.card}>
          <h1 style={styles.title}>Wallet</h1>
          <p style={styles.subTitle}>Current balance</p>
          <div style={styles.balance}>{formatVnd(profile?.walletBalance)}</div>
        </div>

        <form style={styles.card} onSubmit={handleTopUp}>
          <h2 style={styles.sectionTitle}>Add Funds via VNPay</h2>
          <label style={styles.label}>Amount (VND)</label>
          <input
            type="number"
            min="10000"
            step="1000"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={styles.input}
          />
          <button type="submit" disabled={submitting} style={styles.button}>
            {submitting ? 'Redirecting to VNPay...' : 'Top Up with VNPay'}
          </button>
          <p style={styles.hint}>Minimum amount: 10,000 VND</p>
        </form>

        {message && <div style={styles.success}>{message}</div>}
        {error && <div style={styles.error}>{error}</div>}

        <div style={styles.card}>
          <h2 style={styles.sectionTitle}>Recent Transactions</h2>
          {transactions.length === 0 ? (
            <p style={styles.hint}>No transactions yet.</p>
          ) : (
            <>
              <div style={styles.table}>
                {pagedTransactions.map((tx) => (
                  <div key={tx.id} style={styles.row}>
                    <div>
                      <div style={styles.rowTitle}>{getTransactionTypeLabel(tx.type)}</div>
                      <div style={styles.rowMeta}>Order: {tx.orderCode}</div>
                    </div>
                    <div style={styles.rowRight}>
                      <div style={styles.rowAmount}>{formatVnd(tx.amount)}</div>
                      <div style={styles.rowMeta}>{getTransactionStatusLabel(tx.status)}</div>
                    </div>
                  </div>
                ))}
              </div>

              <div style={styles.paginationWrap}>
                <button
                  type="button"
                  style={styles.paginationButton}
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                >
                  Previous
                </button>
                <span style={styles.paginationText}>Page {currentPage} of {totalPages}</span>
                <button
                  type="button"
                  style={styles.paginationButton}
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                >
                  Next
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: 'calc(100vh - 56px)',
    padding: '24px 16px',
    background: '#f3f4f6',
    fontFamily: 'Inter, system-ui, sans-serif',
    display: 'flex',
    justifyContent: 'center',
  },
  container: {
    width: '100%',
    maxWidth: '720px',
    display: 'grid',
    gap: '16px',
  },
  card: {
    background: '#ffffff',
    borderRadius: '14px',
    padding: '20px',
    border: '1px solid #e5e7eb',
  },
  title: {
    margin: 0,
    fontSize: '26px',
    color: '#111827',
  },
  subTitle: {
    margin: '10px 0 6px',
    color: '#6b7280',
    fontSize: '13px',
  },
  balance: {
    fontSize: '32px',
    fontWeight: 700,
    color: '#0f766e',
  },
  sectionTitle: {
    margin: '0 0 14px',
    fontSize: '18px',
    color: '#111827',
  },
  label: {
    display: 'block',
    fontSize: '13px',
    color: '#374151',
    marginBottom: '6px',
  },
  input: {
    width: '100%',
    boxSizing: 'border-box',
    padding: '10px 12px',
    borderRadius: '8px',
    border: '1px solid #d1d5db',
    fontSize: '14px',
    marginBottom: '10px',
  },
  button: {
    border: 'none',
    background: '#111827',
    color: '#fff',
    borderRadius: '8px',
    padding: '10px 14px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  hint: {
    margin: '10px 0 0',
    color: '#6b7280',
    fontSize: '13px',
  },
  success: {
    background: '#ecfdf5',
    border: '1px solid #a7f3d0',
    color: '#065f46',
    borderRadius: '10px',
    padding: '10px 12px',
  },
  error: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    color: '#991b1b',
    borderRadius: '10px',
    padding: '10px 12px',
  },
  table: {
    display: 'grid',
    gap: '10px',
  },
  row: {
    border: '1px solid #e5e7eb',
    borderRadius: '10px',
    padding: '10px 12px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '10px',
  },
  rowTitle: {
    fontWeight: 600,
    color: '#111827',
  },
  rowMeta: {
    color: '#6b7280',
    fontSize: '12px',
  },
  rowRight: {
    textAlign: 'right',
  },
  rowAmount: {
    color: '#111827',
    fontWeight: 700,
  },
  paginationWrap: {
    marginTop: '12px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '10px',
  },
  paginationButton: {
    border: '1px solid #d1d5db',
    background: '#ffffff',
    color: '#111827',
    borderRadius: '8px',
    padding: '8px 12px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  paginationText: {
    fontSize: '13px',
    color: '#4b5563',
    fontWeight: 600,
  },
};
