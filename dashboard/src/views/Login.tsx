import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import clsx from 'clsx';
import { authAPI } from '@/lib/api';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(false);
    setLoading(true);

    try {
      const response = await authAPI.login({
        email,
        password,
      });
      
      if (response && response.access_token) {
        localStorage.setItem('access_token', response.access_token);
        navigate('/workspace');
      }
    } catch (err) {
      // Force 1px red error border state
      setError(true);
      console.error('Login Failed', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      {/* The Authentication Card */}
      <div
        className={clsx(
          "w-full max-w-sm bg-white dark:bg-slate-900 border p-8 shadow-sm transition-colors duration-200",
          error ? "border-rose-600 dark:border-rose-500" : "border-slate-200 dark:border-slate-800"
        )}
      >
        <div className="mb-8">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50 uppercase">
            MeshML Airlock
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Command Center Access
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Identity
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 p-2 font-mono text-sm placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-cyan-600 dark:focus:border-cyan-400 transition-colors"
              placeholder="operator@meshml.internal"
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Passkey
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 p-2 font-mono text-sm placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:border-cyan-600 dark:focus:border-cyan-400 transition-colors"
              placeholder="••••••••••••"
              required
            />
          </div>

          {error && (
            <div className="font-mono text-xs font-bold text-rose-600 dark:text-rose-500 mt-2">
              ERR: INVALID_CREDENTIALS
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-slate-900 dark:bg-slate-50 text-slate-50 dark:text-slate-900 font-medium py-2 px-4 text-sm mt-4 hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? 'AUTHENTICATING...' : 'INITIALIZE'}
          </button>
        </form>
      </div>
    </div>
  );
}
