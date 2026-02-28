"use client";

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-100">
      <form className="w-full max-w-md bg-white p-8 rounded-2xl shadow-lg">
        <h2 className="text-2xl font-semibold mb-6 text-center">Create Account</h2>

        <input className="w-full mb-4 p-3 border rounded-lg" placeholder="Full Name" />
        <input className="w-full mb-4 p-3 border rounded-lg" placeholder="Email" />
        <input className="w-full mb-6 p-3 border rounded-lg" placeholder="Password" />

        <button className="w-full bg-black text-white p-3 rounded-lg">
          Register
        </button>
      </form>
    </div>
  );
}