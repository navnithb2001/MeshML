import { Outlet, Link, useNavigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { ThemeToggle } from '@/components/ThemeToggle';

export default function DashboardLayout() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="h-14 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-4">
            <span className="font-semibold tracking-tight uppercase text-sm text-slate-900 dark:text-slate-50">
              MeshML
            </span>
            <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
              v1.0.0
            </span>
          </div>
          
          <nav className="hidden md:flex items-center space-x-4 text-sm font-medium">
            <Link to="/workspace" className="text-slate-600 dark:text-slate-300 hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors uppercase tracking-wider">
              Workspace
            </Link>
          </nav>
        </div>
        
        <div className="flex items-center space-x-4">
          <ThemeToggle />
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-rose-500 transition-colors uppercase tracking-wider font-medium"
            title="Logout"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
