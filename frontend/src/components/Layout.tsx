import type { ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Upload,
  GitCompareArrows,
  FolderTree,
  Database,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children: ReactNode;
}

const menuItems = [
  { text: 'Ingestion', icon: <Upload className="h-4 w-4" />, path: '/ingestion' },
  { text: 'Matcher', icon: <GitCompareArrows className="h-4 w-4" />, path: '/matcher' },
  { text: 'Taxonomy Viewer', icon: <FolderTree className="h-4 w-4" />, path: '/taxonomy' },
  { text: 'Vector Status', icon: <Database className="h-4 w-4" />, path: '/vector-status' },
];

export default function Layout({ children }: LayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-50 w-64 border-r bg-card hidden md:flex flex-col">
        <div className="flex h-14 items-center border-b px-4">
          <span className="font-semibold text-lg">Taxonomy Rationalization</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-4">
          <ul className="space-y-1 px-2">
            {menuItems.map((item) => (
              <li key={item.text}>
                <Button
                  variant={location.pathname === item.path ? "secondary" : "ghost"}
                  className={cn("w-full justify-start gap-2", location.pathname === item.path && "bg-secondary")}
                  onClick={() => navigate(item.path)}
                >
                  {item.icon}
                  {item.text}
                </Button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 md:pl-64">
        <div className="mx-auto p-6 md:p-8 w-full max-w-[2000px]">
            {children}
        </div>
      </main>
    </div>
  );
}
