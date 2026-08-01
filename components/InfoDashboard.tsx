"use client";

import { useCallback, useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type LoadState = "idle" | "requesting" | "loading" | "ready" | "denied" | "error";

interface WeatherInfo {
  tempC: number;
  description: string;
  emoji: string;
}

interface NewsArticle {
  title: string;
  source: string;
}

// Minimal subset of WMO weather codes (Open-Meteo uses this table) — enough
// for a quick glance, not exhaustive.
const WEATHER_CODES: Record<number, { description: string; emoji: string }> = {
  0: { description: "Clear sky", emoji: "☀️" },
  1: { description: "Mostly clear", emoji: "🌤️" },
  2: { description: "Partly cloudy", emoji: "⛅" },
  3: { description: "Overcast", emoji: "☁️" },
  45: { description: "Fog", emoji: "🌫️" },
  48: { description: "Fog", emoji: "🌫️" },
  51: { description: "Light drizzle", emoji: "🌦️" },
  61: { description: "Light rain", emoji: "🌧️" },
  63: { description: "Rain", emoji: "🌧️" },
  65: { description: "Heavy rain", emoji: "🌧️" },
  71: { description: "Light snow", emoji: "🌨️" },
  80: { description: "Rain showers", emoji: "🌦️" },
  95: { description: "Thunderstorm", emoji: "⛈️" },
};

function describeWeatherCode(code: number): { description: string; emoji: string } {
  return WEATHER_CODES[code] || { description: "Unknown", emoji: "🌡️" };
}

export function InfoDashboard() {
  const [state, setState] = useState<LoadState>("idle");
  const [place, setPlace] = useState<string>("");
  const [weather, setWeather] = useState<WeatherInfo | null>(null);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [newsNote, setNewsNote] = useState<string>("");

  const load = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setState("error");
      return;
    }
    setState("requesting");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setState("loading");
        const { latitude, longitude } = pos.coords;

        try {
          const [weatherRes, geoRes] = await Promise.all([
            fetch(
              `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,weather_code`,
            ),
            fetch(
              `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`,
            ),
          ]);

          const weatherData = await weatherRes.json();
          const geoData = await geoRes.json();

          const code = weatherData?.current?.weather_code ?? -1;
          const { description, emoji } = describeWeatherCode(code);
          setWeather({
            tempC: Math.round(weatherData?.current?.temperature_2m ?? 0),
            description,
            emoji,
          });

          const city = geoData?.city || geoData?.locality || "";
          const country = geoData?.countryName || "";
          const placeLabel = [city, country].filter(Boolean).join(", ");
          setPlace(placeLabel);

          try {
            const newsRes = await fetch(
              `${BACKEND_URL}/local_news?query=${encodeURIComponent(city || country || "world")}`,
            );
            const newsData = await newsRes.json();
            setNews(newsData.articles || []);
            setNewsNote(newsData.note || "");
          } catch {
            setNewsNote("Couldn't reach the backend for local news.");
          }

          setState("ready");
        } catch {
          setState("error");
        }
      },
      () => setState("denied"),
      { timeout: 10000 },
    );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="hud hud-dashboard">
      <div className="dashboard-header">AROUND YOU</div>

      {state === "requesting" && <div className="dashboard-note">Requesting location…</div>}
      {state === "loading" && <div className="dashboard-note">Loading…</div>}
      {state === "denied" && (
        <div className="dashboard-note">
          Location permission denied.{" "}
          <button type="button" className="dashboard-retry" onClick={load}>
            Retry
          </button>
        </div>
      )}
      {state === "error" && (
        <div className="dashboard-note">
          Couldn't load this.{" "}
          <button type="button" className="dashboard-retry" onClick={load}>
            Retry
          </button>
        </div>
      )}

      {state === "ready" && (
        <>
          {place && <div className="dashboard-place">{place}</div>}
          {weather && (
            <div className="dashboard-weather">
              <span className="dashboard-weather-emoji">{weather.emoji}</span>
              <span>{weather.tempC}°C</span>
              <span className="dashboard-weather-desc">{weather.description}</span>
            </div>
          )}
          {news.length > 0 ? (
            <ul className="dashboard-news">
              {news.slice(0, 4).map((a, i) => (
                <li key={i}>
                  {a.title}
                  {a.source ? <span className="dashboard-news-source"> · {a.source}</span> : null}
                </li>
              ))}
            </ul>
          ) : (
            newsNote && <div className="dashboard-note">{newsNote}</div>
          )}
        </>
      )}
    </div>
  );
}
