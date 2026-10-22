"use client";
// The small "around you" panel: weather + headlines for where you are.
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Dashboard as Data } from "@/lib/types";

export function useLocation() {
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  useEffect(() => {
    navigator.geolocation?.getCurrentPosition(
      (p) => setCoords({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => {},
      { timeout: 8000, maximumAge: 600000 },
    );
  }, []);
  return coords;
}

export default function Dashboard({ coords, online }: { coords: { lat: number; lon: number } | null; online: boolean }) {
  const [data, setData] = useState<Data | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.dashboard(coords?.lat, coords?.lon));
    } catch {
      setData(null);
    }
  }, [coords]);

  useEffect(() => {
    if (!online) return;
    load();
    const id = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, [load, online]);

  if (!data) return null;
  return (
    <div className="panel around">
      <div className="label">AROUND YOU</div>
      <div className="place">{data.place}</div>
      {data.weather ? (
        <div className="weather">
          {data.weather.temp_c}°C · {data.weather.text}
          <span className="dim"> · feels {data.weather.feels_c}° · {data.weather.humidity}% humidity</span>
        </div>
      ) : (
        <div className="dim">weather unavailable</div>
      )}
      {data.news.length > 0 && (
        <ul className="news">
          {data.news.map((n, i) => (
            <li key={i}>{n.title}<span className="dim"> {n.source}</span></li>
          ))}
        </ul>
      )}
    </div>
  );
}
