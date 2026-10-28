import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { InboxPage } from '../pages/InboxPage';
import { DetailPage } from '../pages/DetailPage';
import { DocumentViewerPage } from '../pages/DocumentViewerPage';
import { LoginPage } from '../pages/LoginPage';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = ({ children }: { children: React.ReactElement }) => {
  const { user } = useAuth();
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><InboxPage /></ProtectedRoute>} />
      <Route path="/radicado/:radicado" element={<ProtectedRoute><DetailPage /></ProtectedRoute>} />
      <Route path="/radicado/:radicado/documento/:documentId" element={<ProtectedRoute><DocumentViewerPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
