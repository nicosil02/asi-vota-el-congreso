import React from "react";
import { Composition } from "remotion";
import guion from "../guion.json";
import { Semana, duracion, type Guion } from "./Semana";

export const Root: React.FC = () => (
  <Composition
    id="Semana"
    component={Semana}
    durationInFrames={duracion(guion as Guion)}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{ guion: guion as Guion }}
  />
);
