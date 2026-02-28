import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import LiveMap from './pages/LiveMap';
import WalletDashboard from './pages/WalletDashboard';
import ProfilePage from './pages/AdminDashboard';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import { authService } from './services/api';

function NavBar({ user, onLogout }) {
  const location = useLocation();

  const publicLinks = [
    { to: '/map', label: 'Live Map' },
  ];

  const authLinks = [
    { to: '/map', label: 'Live Map' },
    { to: '/wallet', label: 'Wallet' },
    { to: '/profile', label: 'Profile' },
  ];

  const links = user ? authLinks : publicLinks;

  return (
    <nav style={navStyles.bar}>
      <Link to="/" style={{ textDecoration: 'none' }}>
        <span style={navStyles.brand}>SmartPark</span>
      </Link>

      <div style={navStyles.links}>
        {links.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            style={
              location.pathname === to
                ? { ...navStyles.link, ...navStyles.linkActive }
                : navStyles.link
            }
          >
            {label}
          </Link>
        ))}

        {!user && (
          <Link
            to="/login"
            style={
              location.pathname === '/login'
                ? { ...navStyles.loginBtn, ...navStyles.loginBtnActive }
                : navStyles.loginBtn
            }
          >
            Sign In
          </Link>
        )}
      </div>
    </nav>
  );
}

function ProtectedRoute({ user, children }) {
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

const navStyles = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 24px',
    height: '56px',
    background: '#ffffff',
    borderBottom: '1px solid #e5e7eb',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  brand: {
    fontSize: '18px',
    fontWeight: 700,
    color: '#111827',
  },
  links: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  link: {
    padding: '6px 16px',
    borderRadius: '8px',
    fontSize: '14px',
    fontWeight: 500,
    color: '#6b7280',
    textDecoration: 'none',
    transition: 'all 0.2s',
  },
  linkActive: {
    background: '#f3f4f6',
    color: '#111827',
    fontWeight: 600,
  },
  loginBtn: {
    padding: '6px 18px',
    borderRadius: '8px',
    fontSize: '14px',
    fontWeight: 600,
    color: '#ffffff',
    background: '#111827',
    textDecoration: 'none',
    transition: 'all 0.2s',
    marginLeft: '4px',
  },
  loginBtnActive: {
    background: '#374151',
  },
};

export default function App() {
  const [user, setUser] = useState(authService.getCurrentUser());

  const handleLogin = (data) => setUser(data);
  const handleLogout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <BrowserRouter>
      <NavBar user={user} onLogout={handleLogout} />
      <Routes>
        {/* Public */}
        <Route path="/map" element={<LiveMap />} />
        <Route path="/login" element={
          user ? <Navigate to="/profile" replace /> : <LoginPage onLogin={handleLogin} />
        } />
        <Route path="/register" element={
          user ? <Navigate to="/profile" replace /> : <RegisterPage onLogin={handleLogin} />
        } />

        {/* Protected */}
        <Route path="/wallet" element={
          <ProtectedRoute user={user}>
            <WalletDashboard />
          </ProtectedRoute>
        } />
        <Route path="/profile" element={
          <ProtectedRoute user={user}>
            <ProfilePage onLogout={handleLogout} />
          </ProtectedRoute>
        } />

        {/* Default */}
        <Route path="*" element={<LiveMap />} />
      </Routes>
    </BrowserRouter>
  );
}
