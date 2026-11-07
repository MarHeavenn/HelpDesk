import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/context/AuthContext'
import LoginPage from '@/pages/LoginPage'
import ProvisionalHome from '@/pages/ProvisionalHome'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<ProvisionalHome />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
