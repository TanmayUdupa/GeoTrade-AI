export default function Dashboard() {
  return (
    <div className="min-h-screen bg-zinc-50 p-10">
      <h1 className="text-3xl font-semibold mb-6">Dashboard</h1>

      <div className="grid md:grid-cols-3 gap-6">
        <a href="/product" className="p-6 bg-white rounded-xl shadow hover:shadow-lg">
          Add New Product
        </a>

        <div className="p-6 bg-white rounded-xl shadow">
          View Predictions
        </div>

        <div className="p-6 bg-white rounded-xl shadow">
          Market Insights
        </div>
      </div>
    </div>
  );
}