"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function ProductPage() {
  const router = useRouter();

  const [form, setForm] = useState({
    name: "",
    category: "",
    costPrice: "",
    weight: "",
    originCountry: ""
  });

  const handleSubmit = async (e: any) => {
    e.preventDefault();

    const res = await fetch("/api/predict", {
      method: "POST",
      body: JSON.stringify(form),
    });

    const data = await res.json();
    localStorage.setItem("results", JSON.stringify(data));
    router.push("/results");
  };

  return (
    <div className="min-h-screen p-10 bg-zinc-50">
      <form onSubmit={handleSubmit} className="max-w-xl mx-auto bg-white p-8 rounded-xl shadow">
        <h2 className="text-2xl font-semibold mb-6">Product Details</h2>

        <input className="w-full mb-4 p-3 border rounded-lg"
          placeholder="Product Name"
          onChange={(e)=>setForm({...form,name:e.target.value})}
        />

        <input className="w-full mb-4 p-3 border rounded-lg"
          placeholder="Category"
          onChange={(e)=>setForm({...form,category:e.target.value})}
        />

        <input className="w-full mb-4 p-3 border rounded-lg"
          placeholder="Cost Price"
          onChange={(e)=>setForm({...form,costPrice:e.target.value})}
        />

        <input className="w-full mb-4 p-3 border rounded-lg"
          placeholder="Weight (kg)"
          onChange={(e)=>setForm({...form,weight:e.target.value})}
        />

        <input className="w-full mb-6 p-3 border rounded-lg"
          placeholder="Origin Country"
          onChange={(e)=>setForm({...form,originCountry:e.target.value})}
        />

        <button className="w-full bg-black text-white p-3 rounded-lg">
          Predict Best Markets
        </button>
      </form>
    </div>
  );
}