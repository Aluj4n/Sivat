import React from 'react';
import { Search } from 'lucide-react';
import './Header.css';
import logocanaln from '../../assets/logo-canalN.webp';

const Header: React.FC = () => {
  return (
    <header className="canal-n-header">
      <div className="header-content">
        <div className="header-left">
          <div className="logo-container">
            <img src={logocanaln} alt="Logo Canal N" className="logo" />
          </div>
          <nav className="main-nav">
            <ul>
              <li><a href="#actualidad">ACTUALIDAD</a></li>
              <li><a href="#peru">PERÚ</a></li>
              <li><a href="#internacionales">INTERNACIONALES</a></li>
              <li><a href="#deportes">DEPORTES</a></li>
            </ul>
          </nav>
        </div>
        
        <div className="header-right">
          <div className="alerta-noticias">
            <span className="hashtag">#</span>AlertaNoticias
          </div>
          <div className="whatsapp-contact">
            {/* WhatsApp Icon (using a simple SVG since lucide doesn't have the exact original whatsapp logo, or using a generic message/phone icon. Actually, lucide-react might not have 'Whatsapp' so I'll use an inline SVG for WhatsApp) */}
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              className="whatsapp-icon"
            >
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
            </svg>
            <span className="phone-number">998-131604</span>
          </div>
          <button className="search-button" aria-label="Buscar">
            <Search size={20} />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
