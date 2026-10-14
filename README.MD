# DuckyEscape Arenas

Módulo de **escape rooms educativas** de la plataforma [DuckyArenas](../), desarrollado por el Equipo 4.

---

## ¿Qué es DuckyEscape?

DuckyEscape es uno de los cuatro sectores de juego de DuckyArenas. El jugador explora habitaciones encadenadas, resuelve puzzles técnicos y obtiene fragmentos de solución que le permiten avanzar y finalmente escapar antes de que se acabe el tiempo.

- **Público:** alumnado y profesorado de tecnología.
- **Modo de juego:** individual (MVP); cooperativo en fases posteriores.
- **Temáticas:** Full Stack, Python, Django, JavaScript, ReactJS, SQL, PostgreSQL, Git/GitHub, Scrum, Regex.

---

## Estructura de datos

La jerarquía de modelos sigue la cadena:

```
EscapeRoom → Room → Stage → Puzzle → Hint
                       └→ StageAsset
```

### Modelos de contenido

| Modelo       | Descripción                                                                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `EscapeRoom` | Sala temática completa. Tiene dificultad, duración estimada, tiempo límite y hash de la solución final.                                          |
| `Room`       | Habitación dentro de una EscapeRoom. Tiene orden, hash de puerta y un fragmento final que sólo se revela al abrirla.                             |
| `Stage`      | Fase dentro de una Room. Tipos: `INTRO`, `PUZZLE`, `LOCK`, `FINAL`. Lleva `completion_condition` en JSON.                                        |
| `Puzzle`     | Reto concreto. Tipos: `TEXT`, `NUMBER`, `MULTIPLE_CHOICE`, `SEQUENCE`, `OBJECT`.                                                                 |
| `Hint`       | Pista para un Puzzle **o** para una Room (nunca ambos a la vez — `CheckConstraint`). Tiene coste en monedas, penalización de tiempo y de puntos. |
| `StageAsset` | Recurso multimedia (imagen, audio, vídeo…) adjunto a un Stage.                                                                                   |

### Modelos de sesión y progreso

| Modelo              | Descripción                                                                                                                         |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `UserEscapeSession` | Partida de un usuario en una EscapeRoom. UUID como PK. Estados: `WAITING`, `PLAYING`, `PAUSED`, `COMPLETED`, `FAILED`, `ABANDONED`. |
| `UserRoomProgress`  | Progreso del usuario en cada Room de la partida.                                                                                    |
| `UserStageProgress` | Progreso del usuario en cada Stage. Registra XP bruto, penalización y XP neta.                                                      |
| `PuzzleAttempt`     | Cada intento de respuesta a un Puzzle. La validación ocurre siempre en el servidor.                                                 |
| `HintUsage`         | Uso de una pista: carga monedas, registra penalización de puntuación y de tiempo.                                                   |
| `EscapeSettlement`  | Liquidación final de la sesión: XP bruta, penalizaciones, XP final, bonus y monedas extra.                                          |

---

## Instalación y carga de datos iniciales

### 1. Migraciones

```bash
python manage.py makemigrations escape_arenas
python manage.py migrate
```

### 2. Fixture de seed (contenido de ejemplo)

El fixture incluye 10 EscapeRooms (una por categoría), 30 Rooms, 80 Stages, 60 Puzzles y 62 Hints con contenido en español orientado a tecnología.

```bash
# Copiar el fixture al directorio correcto
cp escape_seed.json apps/escape_arenas/fixtures/

# Cargar los datos
python manage.py loaddata escape_seed.json
```

### Verificar la carga

```bash
# Desde el shell de Django
python manage.py shell -c "
from apps.escape_arenas.models import EscapeRoom, Puzzle, Hint
print('EscapeRooms:', EscapeRoom.objects.count())
print('Puzzles:', Puzzle.objects.count())
print('Hints:', Hint.objects.count())
"
```

---

## Django Admin

Todos los modelos están registrados en `admin.py`. Las relaciones más útiles:

- **EscapeRoom** → inline de Rooms
- **Room** → inline de Stages
- **Stage** → inline de Puzzles y StageAssets
- **Puzzle** → inline de Hints

Accede en `/admin/escape_arenas/`.

---

## URLs y vistas (planificadas)

Basadas en la especificación del TDA (Equipo 5 original, ahora Equipo 4):

```
/escape/                        → listado de EscapeRooms disponibles
/escape/<slug>/                 → detalle de una EscapeRoom
/escape/<slug>/start/           → iniciar sesión
/escape/<slug>/play/            → vista principal de juego
/escape/<slug>/answer/          → enviar respuesta a un puzzle
/escape/<slug>/hint/            → solicitar pista
/escape/<slug>/result/          → resultado final
/escape/history/                → historial de partidas del usuario
```

---

## Reglas de negocio principales

1. **Validación siempre en servidor.** Ni `eval()`, ni `exec()`, ni SQL de usuario contra la base de datos real.
2. **El servidor controla el tiempo.** La expiración de la sesión y los temporizadores de Stage se gestionan en backend; no se acepta tiempo del cliente.
3. **Hashes de solución.** Los campos `solution_hash`, `door_solution_hash` y `final_solution_hash` contienen texto plano en el seed (prefijo `placeholder_*`). En producción se hashean en Fase 2 (responsable: Oriol).
4. **Fragmentos revelados progresivamente.** `Stage.fragment` y `Room.final_fragment` sólo se entregan al cliente una vez superado el desafío correspondiente.
5. **Pistas — exclusión mutua.** Un `Hint` pertenece a un `Puzzle` o a una `Room`, nunca a los dos. Restricción a nivel de base de datos (`CheckConstraint`).
6. **Un `EscapeSettlement` por sesión.** El bonus de escape sólo se concede si el estado final es `COMPLETED`.
7. **Economía integrada.** Las pistas cuestan `DuckyCoins` (gestionadas por DuckyBank/Ecomotor). Las penalizaciones de puntos y tiempo se registran en `HintUsage`.

---

## Flujo de una partida

```
Iniciar sesión (UserEscapeSession)
  └─ Entrar Room 1 (UserRoomProgress)
       └─ Completar Stage INTRO
       └─ Completar Stage PUZZLE
            └─ Resolver Puzzles → PuzzleAttempt(s)
            └─ Pedir Hints (opcional) → HintUsage
       └─ Abrir puerta (Stage LOCK) → obtener door fragment
  └─ Entrar Room 2 ... Room N
  └─ Stage FINAL → combinar fragmentos → validar solución final
EscapeSettlement → XP + DuckyCoins
```

---

## Contribución

- **Rama de desarrollo:** `ernesto` → PR a `development`.
- **Revisores requeridos:** Oriol y Marta (ambos deben aprobar antes del merge).
- **App Django:** `apps.escape_arenas` — label automático: `escape_arenas`.

---

## Notas de versión

| Documento                              | Fecha           | Estado                                                   |
| -------------------------------------- | --------------- | -------------------------------------------------------- |
| TDA Equipo 5 — Especificación original | Sprint 1        | Referencia histórica. Nombres de modelos refactorizados. |
| Modelos Consolidados v1                | 13 oct 2026     | Propuesta técnica pendiente de validación por equipos.   |
| DAR3 — Informe inicial DuckyArenas     | Inicio proyecto | Visión global de la plataforma. Base de arquitectura.    |

> **Aviso:** Los nombres de los modelos evolucionaron entre documentos. La implementación actual (`models.py`) usa los nombres definitivos: `Room` (antes `EscapeStage`), `Stage`, `Puzzle`, `UserEscapeSession` (antes `GameSession`), etc. El documento DAR3 y el TDA original contienen referencias a nombres anteriores que ya no corresponden al código.
