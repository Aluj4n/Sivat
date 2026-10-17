import PanelFeed from '../components/PanelFeed/PanelFeed';

interface Props {
  onIrAValidacion: () => void;
}

export default function Peru({ onIrAValidacion }: Props) {
  return (
    <PanelFeed
      panel="peru"
      titulo="Perú"
      descripcion="Noticias y rumores sobre Perú de medios peruanos (Canal N, RPP, Andina, El Comercio, La República y más), GDELT, Bluesky, Reddit y YouTube. Se actualiza solo y lo no validado se descarta a las 24 h."
      onIrAValidacion={onIrAValidacion}
    />
  );
}
