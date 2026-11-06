# DuckyEscape Arenas

Módulo de **escape rooms educativas** de la plataforma [DuckyArenas](../), desarrollado por el Equipo 4.

---

## ¿Qué es DuckyEscape?

DuckyEscape es uno de los cuatro sectores de juego de DuckyArenas. El jugador entra en un **hub point-and-click con Phaser**, elige una temática (cárcel, colegio, laboratorio…), elige una era histórica (prehistórica, griega, romana… hasta siglo XX) y se adentra en una vista 2D donde un objeto interactuable le abre un puzzle. Resolverlo le hace avanzar por habitaciones encadenadas, obtener fragmentos y finalmente escapar antes de que se acabe el tiempo.

- **Público:** alumnado y profesorado de tecnología.
- **Modo de juego:** individual (MVP); cooperativo en fases posteriores.
- **Temáticas narrativas:** Cárcel, Colegio, Laboratorio (ampliable).
- **Eras históricas (= niveles de dificultad):** Prehistórico (1) → Griego (2) → Romano (3) → Medieval (4) → Renacentista (5) → Rev. Industrial (6) → Siglo XX (7).
- **Dominios técnicos cubiertos por las aventuras:** Full Stack, Python, Django, JavaScript, ReactJS, SQL, PostgreSQL, Git/GitHub, Scrum, Regex.

---

## Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│  Backend Django (apps.escape_arenas)                             │
│                                                                  │
│    models.py      → modelos de contenido y de sesión             │
│    services.py    → motor seguro de juego (start, submit, hint,  │
│                      settlement; nunca eval/exec; valida 1       │
│                      puzzle por stage)                           │
│    views.py       → vistas HTML clásicas + API JSON              │
│    urls.py        → rutas                                        │
│                                                                  │
└────────────────────┬─────────────────────────────────────────────┘
                     │  JSON (cookie de sesión + CSRF)
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│  Frontend Phaser 3 (static/escape_arenas/js/)                    │
│                                                                  │
│    main.js        → bootstrap de Phaser 3 (vía CDN)              │
│    api.js         → helpers fetch con CSRF                       │
│    sfx.js         → efectos de sonido sintéticos (Web Audio API) │
│    scenes/                                                       │
│      BootScene.js   → precarga                                   │
│      HubScene.js    → point-and-click, portales por tema         │
│      ThemeScene.js  → elección de aventura dentro del tema       │
│      RoomScene.js   → juego 2D con objeto interactuable + HUD    │
│    ui/                                                           │
│      puzzle-modal.js → overlay HTML del puzzle                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Punto de entrada del juego:** `/escape/game/` (requiere login).

---

## Estructura de datos

La jerarquía de modelos sigue la cadena:

```
EscapeRoom → Room → Stage → Puzzle → Hint
                       └→ StageAsset
```

### Modelos de contenido

| Modelo       | Descripción                                                                                                                                                                     |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EscapeRoom` | Sala temática completa. Campos clave: `name`, `slug`, `difficulty`, **`theme`** (PRISON/SCHOOL/LAB), **`era`** (1–7), `time_limit_seconds`, `final_solution_hash`, `is_active`. |
| `Room`       | Habitación dentro de una EscapeRoom. Tiene orden, hash de puerta y un fragmento final que sólo se revela al abrirla.                                                            |
| `Stage`      | Fase dentro de una Room. Tipos: `INTRO`, `PUZZLE`, `LOCK`, `FINAL`. Lleva `completion_condition` en JSON.                                                                       |
| `Puzzle`     | Reto concreto. Tipos: `TEXT`, `NUMBER`, `MULTIPLE_CHOICE`, `SEQUENCE`, `OBJECT`. El `config` admite `answer_mode` (`EXACT` o `CASE_INSENSITIVE`).                               |
| `Hint`       | Pista para un Puzzle **o** para una Room (nunca ambos a la vez — `CheckConstraint`). Tiene coste en monedas, penalización de tiempo y de puntos.                                |
| `StageAsset` | Recurso multimedia (imagen, audio, vídeo…) adjunto a un Stage.                                                                                                                  |

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

## Hub y frontend Phaser

El juego se sirve desde `/escape/game/` (vista `game_view`). La template `game.html` carga Phaser 3 por CDN y arranca `main.js` como módulo ES6.

### Escenas

| Escena       | Rol                                                                                                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BootScene`  | Precarga assets globales (actualmente mínima; todo el arte es procedural).                                                                                                                  |
| `HubScene`   | Mundo point-and-click. Un portal por cada tema devuelto por `/api/hub/`. El jugador mueve al pato con flechas y pulsa ENTER para entrar. Los temas sin aventuras activas aparecen apagados. |
| `ThemeScene` | Pantalla intermedia con una tarjeta grande navegable por aventura disponible (flechas ◀ ▶ + ENTER para arrancar partida).                                                                   |
| `RoomScene`  | Vista 2D de la partida en curso: fondo por era, HUD con nombre/era/fase/tiempo/score, botón abandonar y un objeto interactuable que abre el modal del puzzle.                               |

### Puzzle Modal (overlay HTML)

El puzzle se resuelve en un overlay HTML flotante encima del canvas (no dentro de Phaser) para reaprovechar el markup/formularios y porque es más accesible: input de texto o radios según `Puzzle.type`, botones **Pista / Cancelar / Enviar**, feedback con shake y bloque de pista cuando se gasta.

### Iconos y colores por tema

Dentro de una RoomScene, el objeto interactuable varía según `EscapeRoom.theme`:

| Tema   | Emoji | Color  | Etiqueta       |
| ------ | ----- | ------ | -------------- |
| PRISON | 🔑    | rojizo | "la llave"     |
| SCHOOL | 📜    | verde  | "el pergamino" |
| LAB    | ⚗️    | azul   | "el matraz"    |

Y el fondo de RoomScene usa un degradado diferente por era (prehistórico marrón, griego azul, romano rojo, medieval gris, renacentista morado, industrial sepia, siglo XX azul oscuro).

### Efectos de sonido

`sfx.js` genera tonos sintéticos con Web Audio API — cero assets externos. Hay 6 efectos: `open`, `correct`, `wrong`, `hint`, `victory`, `defeat`, disparados desde `RoomScene` en los momentos clave.

---

## API JSON para el frontend

Todos los endpoints requieren login (`@login_required`) y usan la cookie de sesión Django. Los `POST` exigen header `X-CSRFToken` con el valor que inyecta el template `game.html`.

Formato uniforme de respuesta:

- Éxito: `{"ok": true, ...}`
- Error controlado: `{"ok": false, "error": "..."}` con HTTP 400/404/409.

### `GET /escape/api/hub/`

Lista los escape rooms activos agrupados por tema. Siempre devuelve los 3 temas (apagados si no tienen aventuras).

```json
{
  "themes": [
    {
      "key": "PRISON",
      "label": "Cárcel",
      "rooms": [
        {
          "id": 9,
          "slug": "...",
          "name": "...",
          "description": "...",
          "era": 1,
          "era_display": "Prehistórico",
          "difficulty": "EASY",
          "difficulty_display": "Fácil",
          "estimated_duration": 30
        }
      ]
    },
    { "key": "SCHOOL", "label": "Colegio", "rooms": [] },
    { "key": "LAB", "label": "Laboratorio", "rooms": [] }
  ]
}
```

### `POST /escape/api/session/start/`

Arranca una partida en el escape room indicado, o reanuda la activa del usuario.

- **Body:** `{"escape_room_id": <int>}`
- **Respuesta:** `{"ok": true, "session_id": "<uuid>", "resumed": <bool>, "escape_room": {...}}`
- **Errores:** 400 si falta `escape_room_id`, 400 con el `ValueError` de `services.start_session` si el contenido no es válido (ver reglas MVP más abajo).

### `GET /escape/api/session/<uuid:pk>/state/`

Devuelve el estado completo que `RoomScene` necesita para pintarse: `session`, `room`, `stage`, `puzzle`, `hint`, `progress` mientras la partida esté `PLAYING`; `session`, `settlement`, `stats` + `finished: true` si ya terminó.

### `POST /escape/api/session/<uuid:pk>/submit/`

Envía la respuesta al puzzle actual.

- **Body:** `{"puzzle_id": <int>, "answer": <str>}`
- **Respuesta:** `{"ok": true, "is_correct": <bool>, "completed": <bool>, "failed": <bool>, "session_status": "<status>"}`
- **Validación defensiva:** `answer` no puede estar vacía y tiene un máximo de 1000 caracteres.
- **Errores:** 400 si la sesión no está `PLAYING`, 409 si el `puzzle_id` no coincide con el puzzle actual (la fase ha avanzado entre tanto).

### `POST /escape/api/session/<uuid:pk>/hint/`

Usa la siguiente pista disponible en la fase actual.

- **Respuesta:** `{"ok": true, "hint": {"id": N, "order": N, "text": "...", "penalty_seconds": N, "penalty_points": N}}`
- **Errores:** 404 si no hay pistas disponibles.

### `POST /escape/api/session/<uuid:pk>/abandon/`

Marca la sesión como `ABANDONED` y la liquida. Idempotente.

- **Respuesta:** `{"ok": true, "status": "ABANDONED"}`

---

## Cómo crear una aventura jugable

Desde el admin de Django (`/admin/escape_arenas/`), en este orden:

### 1. EscapeRoom

`/admin/escape_arenas/escaperoom/add/`. Rellena:

- `name`, `slug`, `description`, `difficulty`.
- `theme` → PRISON, SCHOOL o LAB.
- `era` → 1 a 7.
- `time_limit_seconds` → p. ej. 1800 (30 min).
- `final_solution_hash` → texto en claro de la solución final (pendiente de hashear en Fase 2).
- `is_active` ✅

### 2. Una o varias Rooms

Desde el inline de EscapeRoom o en `/admin/escape_arenas/room/add/`. Cada Room necesita:

- `order` (empieza en 1).
- `name`, `description`.
- `door_solution_hash`, `final_fragment`.

### 3. Una o varias Stages dentro de cada Room

- `order` (empieza en 1).
- `name`, `description`.
- `type` → PUZZLE (lo habitual), INTRO, LOCK o FINAL.
- `completion_condition` → `{"require": "all_puzzles"}` por defecto.
- `fragment` → texto que se revela al completar.

### 4. **Exactamente 1 Puzzle por Stage** (regla MVP)

- `order` → 1.
- `title`, `description`.
- `type` → TEXT, NUMBER, MULTIPLE_CHOICE…
- `config` → `{"answer_mode": "CASE_INSENSITIVE"}` recomendado. Para MULTIPLE_CHOICE: `{"answer_mode": "CASE_INSENSITIVE", "options": ["A", "B", "C"]}`.
- `solution_hash` → respuesta en claro (sin prefijo `placeholder_`).
- `max_attempts` → opcional (null = ilimitado; p. ej. 5).
- `points` → XP bruta que otorga resolverlo.

### 5. (Opcional) Hints

Una o varias por Puzzle **o** por Room (nunca las dos). Cada Hint tiene `text`, `penalty_seconds`, `penalty_points`, `unlock_after_seconds`.

### Verificar

Entra a `/escape/game/` y navega hasta tu aventura. Si `services.start_session` rechaza el contenido, el frontend muestra el mensaje exacto del error en pantalla (p. ej. "El MVP requiere un puzzle en cada fase.").

---

## Reglas del MVP implementado

Validadas en `services.start_session`:

1. **Exactamente 1 puzzle por Stage.** Stages con 0 o >1 puzzles son rechazadas.
2. **Nada de placeholders.** Un `solution_hash` que empieza por `placeholder_` detiene el arranque.
3. **`answer_mode` admitido:** solo `EXACT` o `CASE_INSENSITIVE`.
4. **MULTIPLE_CHOICE coherente:** `solution_hash` debe estar entre las `options` del `config`.
5. **La EscapeRoom necesita al menos 1 Room con al menos 1 Stage jugable.**

Validadas en `services.register_attempt`:

6. **La respuesta se evalúa en el servidor** con `check_stage_answer` (case-insensitive por defecto).
7. **El `puzzle_id` del cliente se contrasta** con el stage actual antes de registrar intento.
8. **Al acertar**, `_advance` mueve el puntero a la siguiente Stage; si no hay más, cierra la Room; si no hay más Rooms, marca `COMPLETED` y liquida.
9. **Al agotar `max_attempts`**, la sesión pasa a `FAILED` y se liquida.
10. **La expiración por tiempo** la gestiona `expire_session_if_needed`; el reloj del cliente es puramente visual.

---

## Instalación y carga de datos iniciales

### 1. Migraciones

```bash
python manage.py makemigrations escape_arenas
python manage.py migrate
```

### 2. Fixture de seed (contenido histórico)

El fixture original incluye 10 EscapeRooms (una por categoría), 30 Rooms, 80 Stages, 60 Puzzles y 62 Hints con contenido en español orientado a tecnología.

```bash
# Copiar el fixture al directorio correcto
cp escape_seed.json apps/escape_arenas/fixtures/

# Cargar los datos
python manage.py loaddata escape_seed.json
```

> **Aviso:** parte del fixture original tiene Stages con 2 puzzles o `solution_hash` tipo `placeholder_*`, incompatibles con la regla MVP del motor actual. Para que una aventura del fixture sea jugable desde Phaser, hay que dividir las Stages y reemplazar los placeholders con soluciones reales desde el admin.

### 3. Crear aventuras compatibles

Lo recomendado desde la introducción del motor MVP y la API es crear las aventuras **a mano desde el admin** siguiendo la guía _"Cómo crear una aventura jugable"_ de más arriba. Cualquier EscapeRoom que cumpla la regla MVP aparecerá automáticamente en el hub de Phaser sin tocar código.

### Verificar la carga

```bash
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

- **EscapeRoom** → inline de Rooms. Campos editables: `theme`, `era`, `is_active`.
- **Room** → inline de Stages
- **Stage** → inline de Puzzles y StageAssets
- **Puzzle** → inline de Hints

Accede en `/admin/escape_arenas/`.

---

## URLs y vistas

### HTML clásico (vistas del catálogo y CRUD)

```
/escape/                        → listado de EscapeRooms (room_list)
/escape/room/<slug>/            → detalle de una EscapeRoom
/escape/room/<slug>/start/      → iniciar sesión (redirige al play)
/escape/session/<uuid>/play/    → vista principal de juego en HTML
/escape/session/<uuid>/submit/  → enviar respuesta (POST)
/escape/session/<uuid>/hint/    → solicitar pista (POST)
/escape/session/<uuid>/result/  → resultado final
/escape/history/                → historial de partidas del usuario
/escape/my-rooms/               → aventuras creadas por el usuario (profesor)
/escape/room/create/            → crear EscapeRoom
/escape/room/<slug>/edit/       → editar
/escape/room/<slug>/delete/     → borrar
/escape/child/...               → CRUD anidado genérico (Room, Stage, Puzzle, Hint)
```

### Frontend Phaser + API JSON

```
/escape/game/                              → canvas de Phaser con hub point-and-click
/escape/api/hub/                           → GET  — lista agrupada por tema
/escape/api/session/start/                 → POST — arranca/reanuda sesión
/escape/api/session/<uuid>/state/          → GET  — estado completo para la escena
/escape/api/session/<uuid>/submit/         → POST — enviar respuesta
/escape/api/session/<uuid>/hint/           → POST — usar pista
/escape/api/session/<uuid>/abandon/        → POST — abandonar partida
```

---

## Reglas de negocio principales

1. **Validación siempre en servidor.** Ni `eval()`, ni `exec()`, ni SQL de usuario contra la base de datos real.
2. **El servidor controla el tiempo.** La expiración de la sesión y los temporizadores de Stage se gestionan en backend; el timer del frontend es cosmético.
3. **Hashes de solución.** Los campos `solution_hash`, `door_solution_hash` y `final_solution_hash` contienen texto plano en el MVP. En producción se hashearán en Fase 2 (responsable: Oriol).
4. **Fragmentos revelados progresivamente.** `Stage.fragment` y `Room.final_fragment` sólo se entregan al cliente una vez superado el desafío correspondiente.
5. **Pistas — exclusión mutua.** Un `Hint` pertenece a un `Puzzle` o a una `Room`, nunca a los dos. Restricción a nivel de base de datos (`CheckConstraint`).
6. **Un `EscapeSettlement` por sesión.** El bonus de escape sólo se concede si el estado final es `COMPLETED`. Incluye bonus por velocidad y por run limpio (sin fallos).
7. **Economía integrada.** Las pistas cuestan `DuckyCoins` (gestionadas por DuckyBank/Ecomotor). Las penalizaciones de puntos y tiempo se registran en `HintUsage`.
8. **CSRF obligatorio en los POST de la API.** La template `game.html` inyecta el token en `window.DUCKY.csrf` y `api.js` lo envía como `X-CSRFToken`.

---

## Flujo de una partida

```
Login en /escape/game/
  └─ HubScene (fetch /api/hub/)
       └─ Elige tema (ENTER sobre portal)
            └─ ThemeScene (navega entre aventuras del tema con ◀ ▶)
                 └─ ENTER → POST /api/session/start/ → UserEscapeSession creada
                      └─ RoomScene (fetch /api/session/<id>/state/)
                           └─ Click en objeto → modal del puzzle (overlay HTML)
                                └─ POST /api/session/<id>/submit/
                                     ├─ correct → scene.restart (próximo stage)
                                     ├─ hint → POST /api/session/<id>/hint/
                                     └─ wrong → shake + reintento
                           └─ Botón abandonar → POST /api/session/<id>/abandon/
                           └─ Timer a 0 → refresh state → derrota
                      └─ Al completar la última Stage → EscapeSettlement →
                         pantalla de VICTORIA con XP bruta, penalización, bonus
                         y XP final.
```

---

## Contribución

- **Rama de desarrollo:** `ernesto` → PR a `development`.
- **Revisores requeridos:** Oriol y Marta (ambos deben aprobar antes del merge).
- **App Django:** `apps.escape_arenas` — label automático: `escape_arenas`.

---

## Notas de versión

| Documento                              | Fecha           | Estado                                                                                            |
| -------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------- |
| TDA Equipo 5 — Especificación original | Sprint 1        | Referencia histórica. Nombres de modelos refactorizados.                                          |
| Modelos Consolidados v1                | 13 oct 2026     | Propuesta técnica validada e implementada.                                                        |
| DAR3 — Informe inicial DuckyArenas     | Inicio proyecto | Visión global de la plataforma. Base de arquitectura.                                             |
| Propuesta Phaser + API JSON            | 4 nov 2026      | Implementada en 05/11/2026.                                                                       |
| Hub + ThemeScene + RoomScene jugables  | 5 nov 2026      | Flujo end-to-end funcional sobre cualquier EscapeRoom creado en el admin que cumpla la regla MVP. |

> **Aviso:** Los nombres de los modelos evolucionaron entre documentos. La implementación actual (`models.py`) usa los nombres definitivos: `Room` (antes `EscapeStage`), `Stage`, `Puzzle`, `UserEscapeSession` (antes `GameSession`), etc. El documento DAR3 y el TDA original contienen referencias a nombres anteriores que ya no corresponden al código.
