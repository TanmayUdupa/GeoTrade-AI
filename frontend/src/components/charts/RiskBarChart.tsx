// frontend/src/components/charts/RiskBarChart.tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { CountryRiskScore } from "../../types";

const COLORS = {
  LOW: "#22c55e",
  MODERATE: "#f59e0b",
  HIGH: "#ef4444",
  CRITICAL: "#dc2626",
};

interface Props {
  data: CountryRiskScore[];
  onSelect: (code: string) => void;
}

export function RiskBarChart({ data, onSelect }: Props) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 0, right: 20, bottom: 0, left: 30 }}
        onClick={(e) => {
          if (e?.activePayload?.[0]) {
            onSelect(e.activePayload[0].payload.country_code);
          }
        }}
      >
        <XAxis
          type="number"
          domain={[0, 100]}
          tick={{ fill: "#6b7280", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="country_code"
          tick={{ fill: "#9ca3af", fontSize: 10, fontFamily: "monospace" }}
          axisLine={false}
          tickLine={false}
          width={28}
        />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 11, fontFamily: "monospace" }}
          formatter={(val: number, _name, props) => [
            `${val.toFixed(1)} — ${props.payload.risk_level}`,
            props.payload.country_name,
          ]}
        />
        <Bar dataKey="risk_score" radius={[0, 3, 3, 0]} maxBarSize={18}>
          {data.map(d => (
            <Cell
              key={d.country_code}
              fill={COLORS[d.risk_level] || "#6b7280"}
              style={{ cursor: "pointer" }}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
