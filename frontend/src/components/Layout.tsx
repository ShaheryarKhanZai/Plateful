import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";

export function Layout() {
  const { user, logout } = useAuth();
  const { count } = useCart();
  const navigate = useNavigate();
  const cls = ({ isActive }: { isActive: boolean }) => (isActive ? "nav-link active" : "nav-link");

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <Link to={user?.role === "staff" ? "/staff" : "/"} className="wordmark">
          <span className="logo" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4" />
            </svg>
          </span>
          Plateful
        </Link>
        <nav aria-label="Main">
          {user?.role === "staff" ? (
            <NavLink to="/staff" className={cls}>Incoming orders</NavLink>
          ) : (
            <>
              <NavLink to="/" end className={cls}>Restaurants</NavLink>
              {user && <NavLink to="/orders" className={cls}>My orders</NavLink>}
              <NavLink to="/cart" className={cls}>
                Cart{count > 0 && <span className="count" aria-label={`${count} items`}>{count}</span>}
              </NavLink>
            </>
          )}
        </nav>
        <div className="account">
          {user ? (
            <>
              <Link to="/profile" className="nav-link">{user.full_name}</Link>
              <button className="btn btn-quiet" onClick={async () => { await logout(); navigate("/"); }}>Log out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link">Log in</Link>
              <Link to="/register" className="btn">Sign up</Link>
            </>
          )}
        </div>
      </header>
      <main id="main" className="page"><Outlet /></main>
      <footer className="footer">
        <strong>Plateful</strong>
        
      </footer>
    </>
  );
}
