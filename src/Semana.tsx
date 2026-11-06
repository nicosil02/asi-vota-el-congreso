import React from "react";
import {
  AbsoluteFill, Series, interpolate, spring, useCurrentFrame, useVideoConfig,
} from "remotion";
import { loadFont as cargarTitular } from "@remotion/google-fonts/Archivo";
import { loadFont as cargarTexto } from "@remotion/google-fonts/Inter";

const { fontFamily: TITULAR } = cargarTitular("normal", { weights: ["800"], subsets: ["latin"] });
const { fontFamily: TEXTO } = cargarTexto("normal", { weights: ["400", "600"], subsets: ["latin"] });

type Fila = { bancada: string; si: number; no: number; abst: number };
// bancadas = null cuando el voto nominal no cuadra con el acta: solo se muestra el total.
export type Voto = { si: number; no: number; abst: number; bancadas: Fila[] | null };
export type Noticia = {
  camara: string;        // "Senado" | "Diputados" | "Comisión de Presupuesto"...
  estado: string;        // "Aprobado" | "En debate" | ...
  titular: string;
  puntos: string[];      // qué cambia, máx. 3
  importa: string;       // por qué importa, una frase
  voto?: Voto | null;
};
export type Guion = { semana: string; portada: string; noticias: Noticia[]; cierre: string };

const C = {
  papel: "#F4F1EA", tinta: "#141414", tenue: "#6B6B6B", linea: "#D9D4C7",
  rojo: "#C8102E", si: "#1F8A5B", no: "#C8102E", abst: "#B9B4A8",
};
const FPS = 30;
const PORTADA = 4 * FPS;
const CIERRE = 4 * FPS;

// Tiempo de lectura: ~3,3 palabras por segundo + 3 s para la animación, entre 8 y 15 s.
export const durNoticia = (n: Noticia) => {
  const palabras = [n.titular, ...n.puntos, n.importa].join(" ").split(/\s+/).length;
  return Math.round(Math.min(15, Math.max(8, palabras / 3.3 + 3)) * FPS);
};
export const duracion = (g: Guion) =>
  PORTADA + CIERRE + g.noticias.reduce((s, n) => s + durNoticia(n), 0);

// Aparece subiendo. `r` = retraso en frames dentro de su escena.
const Entra: React.FC<{ r?: number; style?: React.CSSProperties; children: React.ReactNode }> =
  ({ r = 0, style, children }) => {
    const frame = useCurrentFrame();
    const p = spring({ frame: frame - r, fps: FPS, config: { damping: 200 } });
    return <div style={{ ...style, opacity: p, transform: `translateY(${(1 - p) * 40}px)` }}>{children}</div>;
  };

const Hoja: React.FC<{ semana: string; paso?: string; children: React.ReactNode }> =
  ({ semana, paso, children }) => (
    <AbsoluteFill style={{ background: C.papel, color: C.tinta, fontFamily: TEXTO, padding: "150px 80px 120px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30, fontWeight: 600,
        letterSpacing: 3, textTransform: "uppercase", borderBottom: `3px solid ${C.tinta}`, paddingBottom: 20 }}>
        <span>Congreso del Perú · {semana}</span>
        <span style={{ color: C.rojo }}>{paso}</span>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 44 }}>
        {children}
      </div>
      <div style={{ fontSize: 24, color: C.tenue }}>
        Fuente: actas de votación y transcripciones de las sesiones del Congreso
      </div>
    </AbsoluteFill>
  );

const Leyenda: React.FC<{ v: Voto; grande?: boolean }> = ({ v, grande }) => (
  <div style={{ display: "flex", gap: grande ? 70 : 40, fontSize: grande ? 40 : 34, whiteSpace: "nowrap" }}>
    {([["a favor", v.si, C.si], ["en contra", v.no, C.no], ["abstención", v.abst, C.abst]] as const).map(([k, n, c]) => (
      <span key={k} style={{ display: "flex", flexDirection: grande ? "column" : "row", gap: grande ? 0 : 10 }}>
        <b style={{ color: c, fontFamily: TITULAR, fontSize: grande ? 110 : undefined, lineHeight: 1 }}>{n}</b>{k}
      </span>
    ))}
  </div>
);

// Una fila por bancada, un punto por voto; las filas se encienden de arriba abajo.
const PorBancada: React.FC<{ v: Voto; r: number }> = ({ v, r }) => {
  const frame = useCurrentFrame();
  if (!v.bancadas) return <Entra r={r}><Leyenda v={v} grande /></Entra>;
  return (
    <Entra r={r - 5} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {v.bancadas.map((b, i) => {
        const on = interpolate(frame, [r + i * 5, r + i * 5 + 15], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const puntos = [...Array(b.si).fill(C.si), ...Array(b.no).fill(C.no), ...Array(b.abst).fill(C.abst)];
        return (
          <div key={b.bancada} style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{ width: 300, fontSize: 28, fontWeight: 600, lineHeight: 1.1 }}>{b.bancada}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, flex: 1 }}>
              {puntos.map((c, j) => (
                <div key={j} style={{ width: 22, height: 22, borderRadius: "50%", background: c, opacity: on }} />
              ))}
            </div>
          </div>
        );
      })}
      <div style={{ marginTop: 10 }}><Leyenda v={v} /></div>
    </Entra>
  );
};

const Tarjeta: React.FC<{ n: Noticia }> = ({ n }) => (
  <>
    <Entra style={{ display: "flex", gap: 18, alignItems: "center", fontSize: 32, fontWeight: 600,
      letterSpacing: 2, textTransform: "uppercase" }}>
      <span>{n.camara}</span>
      <span style={{ background: C.rojo, color: C.papel, padding: "6px 16px", borderRadius: 6 }}>{n.estado}</span>
    </Entra>
    <Entra r={5} style={{ fontFamily: TITULAR, fontWeight: 800, fontSize: 82, lineHeight: 1.04 }}>
      {n.titular}
    </Entra>
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {n.puntos.map((p, i) => (
        <Entra key={i} r={18 + i * 10} style={{ fontSize: 42, lineHeight: 1.3, display: "flex", gap: 20 }}>
          <span style={{ color: C.rojo, fontWeight: 600 }}>—</span><span>{p}</span>
        </Entra>
      ))}
    </div>
    {n.voto && <PorBancada v={n.voto} r={50} />}
    <Entra r={70} style={{ borderLeft: `8px solid ${C.rojo}`, paddingLeft: 28, fontSize: 40,
      lineHeight: 1.3, fontWeight: 600 }}>
      {n.importa}
    </Entra>
  </>
);

export const Semana: React.FC<{ guion: Guion }> = ({ guion: g }) => (
  <Series>
    <Series.Sequence durationInFrames={PORTADA}>
      <Hoja semana={g.semana}>
        <Entra style={{ fontSize: 36, fontWeight: 600, color: C.rojo, letterSpacing: 3, textTransform: "uppercase" }}>
          Resumen legislativo
        </Entra>
        <Entra r={6} style={{ fontFamily: TITULAR, fontWeight: 800, fontSize: 120, lineHeight: 1 }}>
          {g.portada}
        </Entra>
        <Entra r={14} style={{ fontSize: 44, color: C.tenue }}>
          {g.noticias.length} cosas que pasaron esta semana
        </Entra>
      </Hoja>
    </Series.Sequence>

    {g.noticias.map((n, i) => (
      <Series.Sequence key={i} durationInFrames={durNoticia(n)}>
        <Hoja semana={g.semana} paso={`${i + 1}/${g.noticias.length}`}><Tarjeta n={n} /></Hoja>
      </Series.Sequence>
    ))}

    <Series.Sequence durationInFrames={CIERRE}>
      <Hoja semana={g.semana}>
        <Entra style={{ fontFamily: TITULAR, fontWeight: 800, fontSize: 96, lineHeight: 1.05 }}>{g.cierre}</Entra>
        <Entra r={15} style={{ fontSize: 46, color: C.rojo, fontWeight: 600 }}>
          Cada semana, lo que hizo el Congreso y por qué importa.
        </Entra>
      </Hoja>
    </Series.Sequence>
  </Series>
);
