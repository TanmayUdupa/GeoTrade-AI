"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    setError("");

    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await res.json();
    setLoading(false);

    if (res.ok) {
      router.push("/dashboard");
    } else {
      setError(data.message || "Login failed");
    }
  };

  return (
    <div style={{
      display: "flex", justifyContent: "center",
      alignItems: "center", height: "100vh", background: "#f5f5f5"
    }}>
      <div style={{
        background: "white", padding: "40px",
        borderRadius: "8px", width: "360px",
        boxShadow: "0 2px 12px rgba(0,0,0,0.1)"
      }}>
        <h2 style={{ marginBottom: "24px", textAlign: "center" }}>Login</h2>

        {error && (
          <p style={{ color: "red", marginBottom: "16px", textAlign: "center" }}>
            {error}
          </p>
        )}

        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          style={{ width: "100%", padding: "10px", marginBottom: "12px",
            border: "1px solid #ddd", borderRadius: "4px", boxSizing: "border-box" }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLogin()}
          style={{ width: "100%", padding: "10px", marginBottom: "20px",
            border: "1px solid #ddd", borderRadius: "4px", boxSizing: "border-box" }}
        />
        <button
          onClick={handleLogin}
          disabled={loading}
          style={{ width: "100%", padding: "10px", background: "#0070f3",
            color: "white", border: "none", borderRadius: "4px",
            cursor: "pointer", fontSize: "16px" }}
        >
          {loading ? "Logging in..." : "Login"}
        </button>
      </div>
    </div>
  );
}

