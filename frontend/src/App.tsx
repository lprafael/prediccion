import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Dashboard } from './pages/Dashboard';
import { NuevoPartido } from './pages/NuevoPartido';
import { PartidoLive } from './pages/PartidoLive';
import { Apuestas } from './pages/Apuestas';
import { Calibracion } from './pages/Calibracion';
import { ForebetValueBets } from './pages/ForebetValueBets';
import { getPartidos } from './api/client';


export function App() {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null);
  const isWsConnected = true;

  // If user clicks "En Vivo" tab and no match is selected, find the most recent live match
  const handleTabChange = async (tab: string) => {
    if (tab === 'live' && !selectedMatchId) {
      try {
        const partidos = await getPartidos(10);
        const liveMatch = partidos.find((p) => p.estado === 'en_curso') || partidos[0];
        if (liveMatch) {
          setSelectedMatchId(liveMatch.id);
        }
      } catch (err) {
        console.error(err);
      }
    }
    setCurrentTab(tab);
  };

  const handleSelectMatch = (id: number) => {
    setSelectedMatchId(id);
    setCurrentTab('live');
  };

  const handleMatchCreated = (id: number) => {
    setSelectedMatchId(id);
    setCurrentTab('live');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        currentTab={currentTab}
        onTabChange={handleTabChange}
        isWsConnected={isWsConnected}
      />

      <main style={{ flex: 1, paddingBottom: '40px' }}>
        {currentTab === 'dashboard' && (
          <Dashboard
            onSelectMatch={handleSelectMatch}
            onNavigateNew={() => setCurrentTab('nuevo')}
          />
        )}

        {currentTab === 'nuevo' && (
          <NuevoPartido
            onMatchCreated={handleMatchCreated}
            onCancel={() => setCurrentTab('dashboard')}
          />
        )}

        {currentTab === 'live' && (
          selectedMatchId ? (
            <PartidoLive
              matchId={selectedMatchId}
              onBack={() => setCurrentTab('dashboard')}
            />
          ) : (
            <div style={{ maxWidth: '800px', margin: '60px auto', textAlign: 'center', padding: '24px' }}>
              <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '10px' }}>
                No hay partido seleccionado para visualización en vivo
              </h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Selecciona un partido desde el panel o crea uno nuevo para conectar el motor de simulación.
              </p>
              <button onClick={() => setCurrentTab('dashboard')} className="btn-primary">
                Ver Lista de Partidos
              </button>
            </div>
          )
        )}

        {currentTab === 'apuestas' && <Apuestas />}

        {currentTab === 'forebet' && <ForebetValueBets />}

        {currentTab === 'calibracion' && <Calibracion />}
      </main>


      <footer style={{
        textAlign: 'center',
        padding: '16px',
        borderTop: '1px solid var(--border-subtle)',
        color: 'var(--text-muted)',
        fontSize: '0.78rem'
      }}>
        Poliverso Basketball Predictor v2.0 · Motor Bayesiano + Monte Carlo + Deep Learning Residual · FastAPI & React
      </footer>
    </div>
  );
}

export default App;
