Primero hay que registrarse en http://127.0.0.1:8000/accounts/register/ después hacer login e ir a http://127.0.0.1:8000/escape/ 
En el catálogo aparece Full Stack Lockdown, esta es la DEMO para ver el funcionamiento de todo

| Fase | Contenido | Respuesta para la demo |
| --- | --- | --- |
| 1 | Selector de id CSS | `#salida` |
| 2 | Arrays JavaScript | `6` |
| 3 | Generador Python | `18` |
| 4 | Propietario en Django | Seleccionar `user=request.user` |
| 5 | Consulta SQL | Seleccionar `SELECT nombre FROM jugadores WHERE activo = TRUE;` |
| 6 | Estado de Git | `git status` |
| 7 | Planificación Scrum | `Sprint Planning` |
| 8 | PIN de cuatro dígitos | Seleccionar `^[0-9]{4}$` |

Los retos aplican conceptos a una historia común. SQL y regex se corrigen por
comparación textual de la opción; no se ejecuta la respuesta del jugador.

## Prueba de seguridad

```bash
python manage.py test apps.escape_arenas.tests.EscapeTests.test_other_user_blocked
```

