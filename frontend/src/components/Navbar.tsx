import React from 'react';
import { 
  Flame, 
  LayoutDashboard, 
  PlusCircle, 
  CircleDollarSign, 
  Cpu, 
  Radio, 
  Volume2, 
  VolumeX, 
  Wifi, 
  WifiOff,
  TrendingUp
} from 'lucide-react';
import { sounds } from '../utils/audio';

interface NavbarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  isWsConnected?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onTabChange, isWsConnected }) => {
  const [soundEnabled, setSoundEnabled] = React.useState(sounds.enabled);

  const toggleSound = () => {
    sounds.enabled = !soundEnabled;
    setSoundEnabled(sounds.enabled);
    if (sounds.enabled) {
      sounds.playScoreTick();
    }
  };

  const navItems = [
    { id: 'dashboard', label: 'Partidos', icon: LayoutDashboard },
    { id: 'live', label: 'En Vivo', icon: Radio, highlight: true },
    { id: 'forebet', label: 'Value Bets Forebet', icon: TrendingUp },
    { id: 'nuevo', label: 'Nuevo Partido', icon: PlusCircle },
    { id: 'apuestas', label: 'Apuestas & ROI', icon: CircleDollarSign },
    { id: 'calibracion', label: 'Calibración ML', icon: Cpu },
  ];


  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 50,
      backdropFilter: 'blur(20px)',
      background: 'rgba(9, 13, 22, 0.85)',
      borderBottom: '1px solid var(--border-subtle)',
      padding: '12px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '16px'
    }}>
      {/* Brand */}
      <div 
        onClick={() => onTabChange('dashboard')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          cursor: 'pointer'
        }}
      >
        <div style={{
          width: '40px',
          height: '40px',
          borderRadius: '12px',
          background: 'linear-gradient(135deg, #ff7700 0%, #ff4400 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 20px rgba(255, 119, 0, 0.5)'
        }}>
          <Flame size={24} color="#fff" />
        </div>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.5px' }}>
            POLIVERSO <span style={{ color: 'var(--accent-orange)' }}>BASKET</span>
          </h1>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1px' }}>
            Bayesian & Deep Live Prediction v2.0
          </p>
        </div>
      </div>

      {/* Navigation tabs */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.9rem',
                transition: 'all 0.2s ease',
                background: isActive 
                  ? (item.highlight ? 'linear-gradient(135deg, #ff7700 0%, #ff5500 100%)' : 'var(--bg-surface-elevated)')
                  : 'transparent',
                color: isActive ? '#fff' : 'var(--text-secondary)',
                boxShadow: (isActive && item.highlight) ? '0 4px 15px rgba(255, 119, 0, 0.4)' : 'none',
              }}
            >
              <Icon size={18} color={isActive ? '#fff' : 'var(--text-muted)'} />
              {item.label}
              {item.id === 'live' && <span className="live-pulse" style={{ marginLeft: '4px' }} />}
              {item.id === 'forebet' && (
                <span style={{
                  background: 'rgba(0, 230, 153, 0.25)',
                  color: '#00e699',
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '1px 6px',
                  borderRadius: '4px',
                  marginLeft: '4px'
                }}>
                  +EV
                </span>
              )}
            </button>

          );
        })}
      </nav>

      {/* Right Controls: WS Status & Audio */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* WebSocket status pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 10px',
          borderRadius: '9999px',
          fontSize: '0.78rem',
          fontWeight: 700,
          background: isWsConnected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
          color: isWsConnected ? '#10b981' : '#f43f5e',
          border: `1px solid ${isWsConnected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
        }}>
          {isWsConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
          {isWsConnected ? 'EN LÍNEA' : 'OFFLINE'}
        </div>

        {/* Audio mute toggle */}
        <button
          onClick={toggleSound}
          title={soundEnabled ? 'Silenciar alertas' : 'Activar alertas sonoras'}
          style={{
            background: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '8px',
            cursor: 'pointer',
            color: soundEnabled ? 'var(--accent-orange)' : 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s ease'
          }}
        >
          {soundEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
        </button>
      </div>
    </header>
  );
};
