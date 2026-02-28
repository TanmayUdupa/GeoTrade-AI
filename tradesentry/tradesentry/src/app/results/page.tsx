"use client";
import { useEffect, useState } from "react";

export default function ResultsPage() {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem("results");
    if (stored) setData(JSON.parse(stored));
  }, []);

  return (
    <div className="min-h-screen p-10 bg-zinc-50">
      <h1 className="text-3xl font-semibold mb-6">Country Ranking (Ascending Profit)</h1>

      <div className="space-y-4">
        {data.map((c, index) => (
          <div key={index} className="p-6 bg-white rounded-xl shadow flex justify-between">
            <span>{c.country}</span>
            <span>Profit: ${c.profit.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}