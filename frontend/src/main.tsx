import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles.css'
import { AuthProvider } from './store/AuthContext'
import { LanguageProvider } from './store/LanguageContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><LanguageProvider><BrowserRouter><AuthProvider><App/></AuthProvider></BrowserRouter></LanguageProvider></React.StrictMode>,
)
