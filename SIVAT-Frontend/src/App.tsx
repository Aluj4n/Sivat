import { useState } from 'react';
import Header from './components/Header/Header';
import Busqueda from './views/Busqueda';
import Dashboard from './views/Dashboard';
import Internacionales from './views/Internacionales';
import Peru from './views/Peru';
import Tendencias from './views/Tendencias';
import Validacion from './views/Validacion';
import './App.css';

export type Vista = 'dashboard' | 'peru' | 'internacionales' | 'tendencias' | 'validacion' | 'busqueda';

function App() {
  const [vistaActiva, setVistaActiva] = useState<Vista>('dashboard');

  return (
    <div className="app-container">
      <Header vistaActiva={vistaActiva} onNavigate={setVistaActiva} />
      <main className="main-content">
        {vistaActiva === 'dashboard' && <Dashboard onNavegar={setVistaActiva} />}
        {vistaActiva === 'internacionales' && (
          <Internacionales onIrAValidacion={() => setVistaActiva('validacion')} />
        )}
        {vistaActiva === 'tendencias' && <Tendencias onIrAValidacion={() => setVistaActiva('validacion')} />}
        {vistaActiva === 'validacion' && <Validacion />}
        {vistaActiva === 'peru' && <Peru onIrAValidacion={() => setVistaActiva('validacion')} />}
        {vistaActiva === 'busqueda' && <Busqueda onIrAValidacion={() => setVistaActiva('validacion')} />}
      </main>
    </div>
  );
}

export default App;
