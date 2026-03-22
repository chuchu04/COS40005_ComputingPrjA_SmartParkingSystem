import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:5219/api',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------- Auth helpers ----------

export const authService = {
  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password });
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data));
    return data;
  },

  register: async (userName, email, password) => {
    const { data } = await api.post('/auth/register', { userName, email, password });
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data));
    return data;
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  },

  getProfile: async () => {
    const { data } = await api.get('/auth/profile');
    return data;
  },

  getCurrentUser: () => {
    if (!localStorage.getItem('token')) {
      return null;
    }

    const user = localStorage.getItem('user');
    if (!user) {
      return null;
    }

    try {
      return JSON.parse(user);
    } catch {
      return null;
    }
  },

  isAuthenticated: () => {
    return !!localStorage.getItem('token');
  },
};

export const walletService = {
  createTopUpPaymentUrl: async (amount) => {
    const { data } = await api.post('/wallet/vnpay/create-payment-url', { amount });
    return data;
  },

  getTransactions: async () => {
    const { data } = await api.get('/wallet/transactions');
    return data;
  },
};

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      authService.logout();
      window.dispatchEvent(new Event('auth:unauthorized'));
    }

    return Promise.reject(error);
  },
);

export default api;
