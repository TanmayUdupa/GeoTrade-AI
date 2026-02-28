import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json();

  const countries = [
    { country: "USA", tariff: 10, shipping: 15 },
    { country: "Germany", tariff: 8, shipping: 12 },
    { country: "India", tariff: 5, shipping: 5 },
    { country: "Australia", tariff: 12, shipping: 18 },
  ];

  const cost = Number(body.costPrice);

  const results = countries.map((c) => {
    const totalCost = cost + c.tariff + c.shipping;
    const sellingPrice = cost * 1.5;
    const profit = sellingPrice - totalCost;

    return {
      ...c,
      profit
    };
  });

  results.sort((a, b) => a.profit - b.profit);

  return NextResponse.json(results);
}