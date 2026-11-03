import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, ErrorState, Loading } from "../components/States";
import { useFetch } from "../hooks";
import { cuisineEmoji, themeFor } from "../visuals";

export default function Restaurants() {
  const { data, error, loading, reload } = useFetch(api.restaurants, []);
  const [query, setQuery] = useState("");
  const [cuisine, setCuisine] = useState("All");

  const cuisines = ["All", ...new Set((data ?? []).map((r) => r.cuisine))];
  const q = query.trim().toLowerCase();
  const shown = (data ?? []).filter((r) =>
    (cuisine === "All" || r.cuisine === cuisine) &&
    (!q || `${r.name} ${r.cuisine} ${r.description}`.toLowerCase().includes(q)));

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-pill">Local demo app</span>
          <h1>Cravings, <span className="hl">delivered.</span></h1>
          <p>Pick a kitchen, build your order and watch it travel from the stove to your door.</p>
          <div className="search">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
            </svg>
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
                   placeholder="Search kitchens or cuisines" aria-label="Search restaurants or cuisines" />
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <span className="plate">🍕</span>
          <span className="orbit o1">🍜</span><span className="orbit o2">🥗</span><span className="orbit o3">🍛</span>
        </div>
      </section>

      <div className="section-head">
        <h2 className="section-title">Pick a kitchen</h2>
        {data && data.length > 0 && (
          <div className="chips" role="group" aria-label="Filter by cuisine">
            {cuisines.map((c) => (
              <button key={c} className={cuisine === c ? "chip chip-on" : "chip"} aria-pressed={cuisine === c}
                      onClick={() => setCuisine(c)}>{c}</button>
            ))}
          </div>
        )}
      </div>

      {loading && <Loading label="Finding kitchens" skeleton="cards" />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && (
        <EmptyState title="No restaurants yet">Run the seed script to add the sample restaurants.</EmptyState>
      )}
      {data && data.length > 0 && shown.length === 0 && (
        <EmptyState title="No kitchens match that">
          <button className="btn btn-quiet" onClick={() => { setQuery(""); setCuisine("All"); }}>Clear filters</button>
        </EmptyState>
      )}
      {shown.length > 0 && (
        <ul className="cards">
          {shown.map((r) => {
            const t = themeFor(r.name, r.cuisine);
            return (
              <li key={r.id}>
                <Link to={`/restaurants/${r.id}`} className={r.is_open ? "card" : "card card-closed"}>
                  <span className="card-top" style={{ background: t.gradient }} aria-hidden="true">
                    <span className="card-emoji">{cuisineEmoji(r.cuisine)}</span>
                  </span>
                  <span className="card-body">
                    <span className="card-title-row">
                      <span className="card-title">{r.name}</span>
                      <span className={r.is_open ? "pill pill-open" : "pill pill-closed"}>{r.is_open ? "Open" : "Closed"}</span>
                    </span>
                    <span className="row-meta">{r.cuisine}</span>
                    <span className="muted card-desc">{r.description}</span>
                    <span className="card-cta">{r.is_open ? "View menu" : "See menu"}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
