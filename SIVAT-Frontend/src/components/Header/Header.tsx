import React from 'react';
import { Search } from 'lucide-react';
import './Header.css';
import logocanaln from '../../assets/logo-canalN.webp';
import type { Vista } from '../../App';

interface Props {
  vistaActiva: Vista;
  onNavigate: (vista: Vista) => void;
}

const OPCIONES_NAV: { id: Vista; label: string }[] = [
  { id: 'dashboard', label: 'DASHBOARD' },
  { id: 'peru', label: 'PERÚ' },
  { id: 'internacionales', label: 'INTERNACIONALES' },
  { id: 'tendencias', label: 'TENDENCIAS' },
  { id: 'validacion', label: 'VALIDACIÓN' },
];

const Header: React.FC<Props> = ({ vistaActiva, onNavigate }) => {
  return (
    <header className="canal-n-header">
      <div className="header-content">
        <div className="header-left">
          <div className="logo-container">
            <img src={logocanaln} alt="Logo Canal N" className="logo" />
          </div>
          <nav className="main-nav">
            <ul>
              {OPCIONES_NAV.map((opcion) => (
                <li key={opcion.id}>
                  <a
                    href={`#${opcion.id}`}
                    className={vistaActiva === opcion.id ? 'active' : ''}
                    onClick={(e) => {
                      e.preventDefault();
                      onNavigate(opcion.id);
                    }}
                  >
                    {opcion.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        
        <div className="header-right">
          
          <button className="search-button" aria-label="Buscar">
            <Search size={20} />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
