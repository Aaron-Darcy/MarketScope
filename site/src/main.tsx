import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router';

import { ThemeProvider } from './app/theme';
import { Layout } from './components/Layout';
import { BankPage } from './pages/BankPage';
import { Banks } from './pages/Banks';
import { Comparison } from './pages/Comparison';
import { NotFound } from './pages/NotFound';
import { Overview } from './pages/Overview';
import { Persistence } from './pages/Persistence';
import './styles.css';

const router = createBrowserRouter(
  [
    {
      element: <Layout />,
      children: [
        { index: true, element: <Overview /> },
        { path: 'banks', element: <Banks /> },
        { path: 'banks/:cik', element: <BankPage /> },
        { path: 'comparison', element: <Comparison /> },
        { path: 'persistence', element: <Persistence /> },
        { path: '*', element: <NotFound /> },
      ],
    },
  ],
  { basename: import.meta.env.BASE_URL },
);

const root = document.getElementById('root');
if (!root) throw new Error('index.html has no #root element');

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  </StrictMode>,
);
