import { useState } from 'react';
import Header from './components/Header/Header';
import Internacionales from './views/Internacionales';
import './App.css';

export type Vista = 'dashboard' | 'peru' | 'internacionales' | 'validacion';

function App() {
  const [vistaActiva, setVistaActiva] = useState<Vista>('dashboard');

  return (
    <div className="app-container">
      <Header vistaActiva={vistaActiva} onNavigate={setVistaActiva} />
      <main className="main-content">
        {vistaActiva === 'internacionales' && <Internacionales />}
        {vistaActiva !== 'internacionales' && (
          <div className="vista-pendiente">
            <p>Esta sección aún está en construcción.</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
