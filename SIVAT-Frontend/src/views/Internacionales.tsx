import PanelFeed from '../components/PanelFeed/PanelFeed';

interface Props {
  onIrAValidacion: () => void;
}

export default function Internacionales({ onIrAValidacion }: Props) {
  return (
    <PanelFeed
      panel="internacional"
      titulo="Internacionales"
      descripcion="Noticias y rumores internacionales de GDELT, medios en español (RSS), Bluesky, Reddit y YouTube. Se actualiza solo y lo no validado se descarta a las 24 h."
      onIrAValidacion={onIrAValidacion}
    />
  );
}
