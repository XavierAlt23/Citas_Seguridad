# Texto íntegro extraído del DOCX

Documento original: `Informe_ESPE_Formato_Corregido.docx`. Las tablas se presentan en orden de lectura; las figuras permanecen en el original.









UNIVERSIDAD DE LAS FUERZAS ARMADAS – ESPE

DEPARTAMENTO DE CIENCIAS DE LA COMPUTACIÓN

CARRERA DE INGENIERÍA DE SOFTWARE



INFORME TÉCNICO INTEGRADO

PROPUESTA DE APLICACIÓN SEGURA PARA CONSULTAS MÉDICAS CON SEGUROS





Asignatura: Ing. de la Seguridad de Software

Docente: Ing. Luis Jaramillo

Estudiante: ______________________________

Fecha: 29 de octubre de 2026

Quito – Ecuador



Índice general

Resumen ejecutivo3

1. Alcance y decisiones adoptadas3

2. Requisitos definitivos y casos de uso3

2.1 Depuración de requisitos S01–S143

2.2 Actores y política de acceso5

2.3 Flujo funcional de la reserva5

3. Protección y recorrido de datos6

3.1 Finalidad y mínima información por proceso6

3.2 Inventario y retención propuesta7

3.3 Fundamento regulatorio8

4. Diseño de solución y persistencia8

4.1 Componentes mínimos8

4.2 Integraciones contratables9

4.3 Modelo lógico de base de datos9

4.4 Dimensionamiento y continuidad11

5. Modelo de amenazas y matriz de riesgos11

5.1 Método y escala11

5.2 Riesgos prioritarios: identificación, impacto y valoración12

5.3 Tratamiento y verificación del riesgo residual13

6. Relación con MITRE ATT&CK14

7. Plan de verificación propuesto15

7.1 Criterios para aprobar el prototipo16

8. Defensa de la propuesta al cliente16

9. Conclusiones17

10. Referencias17



Resumen ejecutivo

Se propone una plataforma web responsiva, accesible desde escritorio y móvil, para localizar especialistas, reservar o cancelar citas, consultar cobertura de cinco aseguradoras y gestionar copagos. El objetivo comercial permanece intacto, pero se evita que el registro de usuario funcione como una recolección masiva de información médica. La solución considera 40.000 pacientes, 150 profesionales, 20 establecimientos y una carga máxima declarada de 2.000 usuarios concurrentes.

La propuesta selecciona los controles con mayor efecto: datos mínimos, segregación clínica, autorización por recurso, integraciones con alcance restringido, pagos externalizados, auditoría individual y recuperación comprobable. Para el prototipo académico se utilizarán datos sintéticos, cinco aseguradoras simuladas y una pasarela de pago simulada; el informe no declara implementaciones ni pruebas ya ejecutadas.

1. Alcance y decisiones adoptadas

Aspecto

Decisión de proyecto

Canal

Web responsiva/PWA para escritorio y móvil, con una API única; evita mantener dos aplicaciones divergentes en la primera versión.

Atención clínica

Fuera de la base de reservas. Un sistema clínico segregado retendrá información sanitaria únicamente cuando proceda.

Seguros y pagos

Cinco conectores simulados y pasarela simulada durante el prototipo; interfaces listas para sustitución por proveedores autorizados.

Entregable

Diseño seguro y plan de pruebas. No se presentan resultados de seguridad como si la aplicación estuviera desplegada.

Escala de referencia

40.000 pacientes, 150 especialistas, 20 centros, cinco aseguradoras y hasta 2.000 concurrentes; capacidad sujeta a prueba de carga.



Se adoptan estas decisiones sin solicitar definiciones adicionales al cliente. Para un despliegue real se ejecutarán las validaciones legales, contractuales y de capacidad exigibles, pero ello no impide plantear una solución cerrada y técnicamente defendible.

2. Requisitos definitivos y casos de uso

2.1 Depuración de requisitos S01–S14

ID

Decisión

Requisito definitivo

Justificación

S01

Conservar

Búsqueda, reserva/cancelación, cobertura y copagos.

Conserva el valor central solicitado.

S02

Modificar

Identidad y medio de contacto mínimos al confirmar reserva; consulta de agenda sin registro.

Principio de minimización.

S03

Modificar

Póliza y beneficiario solo si se utiliza seguro; resultado de elegibilidad limitado.

Evita compartir datos ajenos.

S04

Eliminar

No exigir historia clínica para ver horarios; expediente clínico en módulo segregado.

Salud: categoría especialmente protegida.

S05

Eliminar

No solicitar religión, ingresos, empleador, ubicación continua ni agenda telefónica.

No existe finalidad de reserva que lo justifique.

S06

Modificar

Alta de dependientes con verificación de representación y tratamiento diferenciado de menores.

Reduce suplantación y abuso.

S07

Modificar

Conectores autenticados por aseguradora; scopes, antifraude, anti-replay y registros.

Solo información estrictamente necesaria.

S08

Eliminar

Prohibir acceso global entre aseguradoras; acceso solo a solicitudes propias.

Aislamiento por organización.

S09

Modificar

Avisos neutrales sin diagnóstico, póliza ni especialidad en pantalla bloqueada.

Evita exposición accidental.

S10

Eliminar

Sesiones seguras no compartibles; revocación y expiración; sin enlaces con token reutilizable.

Reduce robo/reutilización de sesión.

S11

Eliminar

Pasarela procesa tarjetas; plataforma guarda importe, identificador y estado del cobro.

Minimiza alcance de datos de pago.

S12

Modificar

Cuentas individuales y registro de consulta/cambio/transferencia con actor y resultado.

Trazabilidad y responsabilidad.

S13

Modificar

Separar servicios y backups; definir recuperación y medir disponibilidad.

Elimina punto único de fallo.

S14

Eliminar

Sin retención indefinida ni uso publicitario/IA impuesto; finalidades y plazos diferenciados.

Protección y limitación de finalidad.



Tabla 2.1. Requisitos corregidos y defendidos ante el cliente.



Figura 2.1. Casos de uso derivados de la Tabla 2.1.

2.2 Actores y política de acceso

Rol

Permitido

Prohibido

Paciente / representante

Sus citas, pólizas propias y dependientes validados.

Datos de terceros o menores sin vínculo.

Profesional

Agenda asignada y datos clínicos solo en sistema autorizado.

Expedientes ajenos y detalle de pago.

Recepción

Agenda del establecimiento y estado de reserva/cobro.

Diagnósticos, CVV, historia clínica.

Aseguradora

Elegibilidad de pólizas propias y solicitudes autorizadas.

Base completa de pacientes u otras aseguradoras.

Operador

Métricas, soporte limitado y acciones auditadas.

Consultar contenidos sensibles por defecto.

Pasarela / notificador

Datos mínimos de su operación puntual.

Acceder al resto de expedientes.



Tabla 2.2. Segregación por rol, centro y objeto.

2.3 Flujo funcional de la reserva

El servidor controla disponibilidad, propiedad del recurso, elegibilidad y resultado del pago. La cita queda confirmada solo si el cupo está libre y la transacción puede completarse de forma idempotente.



Figura 2.2. Flujo de reserva con controles de negocio y seguridad.

3. Protección y recorrido de datos

3.1 Finalidad y mínima información por proceso

Proceso

Datos permitidos

Datos excluidos

Búsqueda

Especialidad, centro, horario.

Documento, póliza, historia clínica.

Reserva

Identidad/contacto mínimos, profesional y franja.

Exámenes, diagnósticos y geolocalización permanente.

Cobertura

Póliza, beneficiario, prestación y estado de autorización.

Historia clínica completa o población de otras aseguradoras.

Copago

Orden, importe, estado y referencia PSP.

PAN, CVV y credenciales de tarjeta.

Atención

Información médica pertinente en sistema separado.

Visibilidad a recepción, aseguradoras no habilitadas y módulo de reservas.



Tabla 3.1. Fronteras de datos por finalidad.



Figura 3.1. Flujo de datos restringido, derivado de la Tabla 3.1.

3.2 Inventario y retención propuesta

Datos

Finalidad

Tipo

Conservación / acceso

Nombre y contacto

Reserva

Personal

Cuenta vigente + 12 meses tras cierre; salvo obligación aplicable.

Identificación y edad

Identidad / representación

Personal; menor especial

Solo mientras exista necesidad del vínculo; disociar luego.

Agenda y estado de cita

Prestación del servicio

Puede inferir salud

24 meses operativos propuestos, salvo deber normativo.

Póliza / beneficiario

Verificación de seguro

Confidencial

Vigencia de vínculo + trazabilidad de solicitudes.

Elegibilidad / copago

Autorización y conciliación

Confidencial

24 meses propuestos; obligaciones aplicables prevalecen.

Comprobante transacción

Pago y conciliación

Financiero

Conforme obligaciones contables/tributarias aplicables.

Representación menor

Autorización dependiente

Categoría protegida

Mientras dure vínculo y evidencia indispensable.

Logs mínimos

Auditoría de seguridad

Dato personal técnico

12 meses propuestos, con acceso segregado.

Historia clínica

Atención, no agenda

Salud: categoría especial

No almacenarla en este aplicativo.

Ingresos/religión/geo/contactos

Sin finalidad proporcional

Algunos sensibles

No recolectar ni conservar.

Tarjeta completa/CVV

Procesamiento externo

Pago de alto riesgo

No almacenar en la plataforma.



Tabla 3.2. Plazos de diseño, no sustituyen obligaciones sanitarias y tributarias.

3.3 Fundamento regulatorio

La Ley Orgánica de Protección de Datos Personales (LOPDP) fundamenta la finalidad y la minimización, exige medidas de seguridad y distingue categorías especiales como los datos de salud y de niñas, niños y adolescentes. El consentimiento no es la única base legitimadora, y cuando se utiliza debe ser libre, específico, informado e inequívoco. Se adoptan circuitos y permisos separados para evitar un tratamiento excesivo. Referencias: [L1], [L2], [L3].

El sistema clínico, cuando se incorpore, será responsabilidad del prestador de salud con sus obligaciones de secreto, seguridad y conservación específicas. Ningún plazo operativo aquí propuesto autoriza borrar documentación sujeta a una obligación de conservación ni retener datos indefinidamente.

4. Diseño de solución y persistencia

4.1 Componentes mínimos

Componente

Responsabilidad

Control esencial

PWA web/móvil

Búsqueda, reserva y estado del seguro.

TLS, sesión segura y no exponer secretos.

API central

Orquesta turnos, permisos y pagos.

Autorización por objeto y tasa limitada.

Base relacional

Pacientes, citas, pólizas y referencias.

Cifrado, transacciones, respaldo aislado.

Módulo de auditoría

Eventos de acciones relevantes.

Actores individuales y registros protegidos.

Conectores

Seguros, PSP y notificaciones.

Firma, scopes, timeout e idempotencia.

Gestión operativa

Monitoreo, despliegue y recuperación.

Secretos externos, alertas y restauración probada.



Tabla 4.1. Componentes y medidas de seguridad.



Figura 4.1. Arquitectura lógica de la solución.

4.2 Integraciones contratables

Integración

Datos y respuesta

Política

Aseguradoras (5)

Beneficiario, póliza, prestación → elegible/copago.

Solo solicitudes propias; claves por aliado; reintentos controlados.

Pasarela PSP

Orden, monto → pago autorizado o denegado.

No almacena PAN/CVV; webhook autenticado; idempotente.

Mensajería

Contacto → recordatorio neutro.

Nada de diagnóstico, póliza ni detalle médico.

Consultorios

Disponibilidad / agenda local.

Segregación por centro y sin replica clínica.



Tabla 4.2. Contrato mínimo de integración.



Figura 4.2. Operaciones externas y puntos de validación.

4.3 Modelo lógico de base de datos

Tabla

Campos principales

USUARIO

id_usuario, contacto, rol, estado

CENTRO

id_centro, nombre

PROFESIONAL

id_prof, id_centro, especialidad

FRANJA

id_franja, id_prof, intervalo, estado

CITA

id_cita, id_usuario, id_franja, estado

ASEGURADORA

id_aseguradora, nombre

POLIZA

id_poliza, id_usuario, id_aseguradora, referencia cifrada

COBERTURA

id_cobertura, id_cita, id_poliza, resultado

COPAGO

id_copago, id_cita, id_psp, importe, estado

REPRESENTACION

id_rep, id_usuario, dependiente y validación

AUDITORIA

id_evento, actor, acción, objeto y fecha



Tabla 4.3. Entidades necesarias; no existe tabla de historia clínica.



Figura 4.3. Relaciones principales de la base de datos.

Restricciones esenciales: (1) una franja solo admite una cita confirmada; (2) la transacción de pago posee clave de idempotencia; (3) el usuario y la entidad externa se verifican en cada acceso a un registro; (4) los campos sensibles se cifran; (5) los borrados y transferencias relevantes dejan eventos atribuibles.

4.4 Dimensionamiento y continuidad

Necesidad

Decisión inicial

Medición exigida

2.000 usuarios simultáneos

Balanceador y servicios replicables; no promesa sin medición.

JMeter: p95, throughput, tasa errores, CPU, RAM y conexiones.

40.000 pacientes

Índices por fecha, centro, profesional y póliza.

Plan de consulta y crecimiento BD.

Reservas concurrentes

Bloqueos/transacciones; cupo único.

Prueba de 100 intentos al mismo horario.

Disponibilidad

Backups externos e infraestructura sin falla única crítica.

Simulacro de restauración y monitoreo.

Recuperación

Objetivos propuestos RTO 4 h y RPO 1 h para reserva; sujetos a pruebas.

Registrar tiempo real de recuperación y pérdida de datos.



Tabla 4.4. Objetivos de ingeniería, no garantías aún verificadas.

5. Modelo de amenazas y matriz de riesgos

5.1 Método y escala

Se aplica el ciclo de la Unidad 1 de Notion: activo → amenaza → vulnerabilidad → ataque → impacto → riesgo → control → verificación. CIA guía las consecuencias; STRIDE ayuda a identificar suplantación, manipulación, repudio, divulgación, denegación de servicio y elevación de privilegios. Se diferencia un abuso activo de una decisión de tratamiento de datos excesiva.

Criterio

Escala

Interpretación

Probabilidad (P)

1 a 5

1 excepcional; 2 baja; 3 posible; 4 alta; 5 muy alta.

Impacto (I)

1 a 5

1 limitado; 2 menor; 3 moderado; 4 grave; 5 severo (salud, menores, fuga masiva).

Puntuación

P × I

1–5 bajo; 6–10 medio; 11–15 alto; 16–25 crítico.

Prioridad

P1 / P2 / P3

P1 = crítico; P2 = alto; P3 = medio/bajo, sujeto a tratamiento.

Residual

P e I revisadas

Se asume eficacia del control; debe comprobarse en pruebas, sin declarar éxito previo.



Tabla 5.1. Reglas de valoración semicuantitativa.



Figura 5.1. Ejemplo BOLA siguiendo el método de Notion.

5.2 Riesgos prioritarios: identificación, impacto y valoración

ID / Req.

Activo

Amenaza, debilidad, ataque y consecuencia (CIA)

Riesgo inherente

R01 / S04/S14

Historia clínica

Recolección masiva; BD expuesta por concentración innecesaria; fuga de salud. [C]

4×5=20Crítico/P1

R02 / S08

Datos de asegurados

Aseguradora curiosa; acceso cruzado sin filtrado institucional; divulgación masiva. [C]

5×5=25Crítico/P1

R03 / S06

Identidad de menor

Tercero agrega dependiente solo por cédula; representación falsa y exposición. [C]

4×5=20Crítico/P1

R04 / S10

Sesión

Atacante reusa token compartible; suplantación y acceso a cuenta. [C/I]

4×5=20Crítico/P1

R05 / S11

Medio de pago

Robo de tarjetas almacenadas; fraude y consecuencias regulatorias. [C]

4×5=20Crítico/P1

R06 / S12

Auditoría

Personal con cuenta compartida; se altera dato sin atribución. [I]

5×4=20Crítico/P1

R07 / S13

Servicio y backup

Caída o ransomware en servidor único; pérdida de citas y recuperación. [A]

4×5=20Crítico/P1

R08 / S14

Privacidad de pacientes

Uso obligado en IA/publicidad; tratamiento incompatible con finalidad. [C]

5×5=25Crítico/P1

R09 / S09

Notificaciones

Vista de pantalla bloqueada divulga diagnóstico o póliza. [C]

4×3=12Alto/P2

R10 / S07

Cobertura

Aliado malicioso o mensaje repetido; consulta ajena / falsa autorización. [C/I]

4×4=16Crítico/P1

R11 / S01

Citas

Paciente manipula ID de otra cita sin verificación de propietario; BOLA. [C/I]

4×4=16Crítico/P1

R12 / S01

Cupo de agenda

Solicitudes simultáneas crean doble reserva; sobreventa del turno. [I/A]

4×3=12Alto/P2

R13 / S02/S10

Cuentas

Fuerza bruta o contraseñas filtradas; secuestro de sesión. [C/I]

4×4=16Crítico/P1

R14 / S01/S13

Disponibilidad API

Flujo excesivo agota CPU/conexiones; denegación de reserva. [A]

4×4=16Crítico/P1

R15 / S01

BD de reserva

Entrada manipulada llega a consulta no parametrizada; extracción o alteración. [C/I]

4×5=20Crítico/P1

R16 / S07/S11

Confirmación de pago

Webhook falsificado marca transacción como pagada sin cobro real. [I]

4×5=20Crítico/P1

R17 / S04/S12

Datos de salud

Empleado sin relación asistencial lee expediente ajeno. [C]

4×5=20Crítico/P1

R18 / S12/S13

Secretos/operación

API key en repositorio o logs; tercero obtiene privilegios. [C/I]

4×5=20Crítico/P1

R19 / S14

Retención

Datos sin plazo permanecen consultables o en respaldos. [C]

5×4=20Crítico/P1

R20 / S08/S12

Administración

Recepcionista usa función administrativa sin control. [C/I]

4×5=20Crítico/P1



Tabla 5.2. Registro resumido de 20 riesgos (orden según requisito).

Justificación: P=5 se reserva a exposición estructural o constante; P=4 a abusos factibles por canales disponibles. I=5 corresponde a salud, menores, tarjetas o pérdida generalizada; I=4 a vulneración relevante de datos/operaciones e I=3 a daño operativo limitado. El valor es conservador y se ajustará con evidencia de pruebas.

5.3 Tratamiento y verificación del riesgo residual

ID

Control prioritario (preventivo/detectivo/correctivo)

Prueba propuesta

Residual*

R01

No capturar expedientes en reserva; separación clínica.

Revisar esquema y formularios: ningún campo clínico.

1×5=5Bajo/P3

R02

Permisos por aseguradora, póliza y solicitud.

Aliado A no puede consultar póliza de B.

1×5=5Bajo/P3

R03

Verificación de vínculo y representación antes de alta.

Alta sin evidencia rechazada.

2×4=8Medio/P3

R04

Cookies seguras, sesión revocable, sin token por URL.

Token expirado/reutilizado inválido.

1×5=5Bajo/P3

R05

Externalizar tarjeta al PSP; guardar solo estado.

DDL, red y logs sin PAN/CVV.

1×5=5Bajo/P3

R06

Cuentas propias, logs de cambios y monitoreo.

Dos funcionarios dejan identidades distintas.

2×4=8Medio/P3

R07

Réplicas, copias aisladas y plan de recuperación.

Restauración medida frente a RTO/RPO.

2×4=8Medio/P3

R08

Eliminar finalidad secundaria del proceso de registro.

Política y datos no habilitan marketing forzoso.

1×5=5Bajo/P3

R09

Plantillas neutrales y privacidad móvil.

Captura de pantalla bloqueada sin detalle.

1×3=3Bajo/P3

R10

Scopes por partner, firma, nonce e idempotencia.

Replay y firma inválida rechazados.

2×4=8Medio/P3

R11

Autorización por objeto en cada ruta.

Paciente A recibe 403/404 para cita B.

1×4=4Bajo/P3

R12

Transacción y restricción única de franja.

100 solicitudes: exactamente una confirmación.

1×3=3Bajo/P3

R13

MFA, límite de intentos, alertas y hash seguro.

Ataque de prueba sintético limitado/detectado.

2×4=8Medio/P3

R14

Rate limit, cuotas, timeouts y colas.

Carga controlada: degradación limitada.

2×3=6Medio/P3

R15

Consultas parametrizadas, validación y mínimo privilegio.

Pruebas de inyección no modifican datos.

1×5=5Bajo/P3

R16

Firma de PSP, validar monto/evento/estado.

Webhook ilegítimo devuelve error, sin cobrar.

1×5=5Bajo/P3

R17

Separación clínica, mínimo privilegio, auditoría.

Recepción no ve datos clínicos.

2×4=8Medio/P3

R18

Vault, secret scanning, rotación y masking.

Escaneo de repositorio y prueba de logs.

2×4=8Medio/P3

R19

Plazos por categoría, borrado/disociación programados.

Prueba de vencimiento y propagación a copias.

2×4=8Medio/P3

R20

Control por función y doble revisión de roles.

Rol recepción no puede elevar privilegios.

2×4=8Medio/P3



Tabla 5.3. Riesgo residual estimado: condicionado a controles efectivos.

La defensa combina controles preventivos (autorización, MFA, cifrado y minimización), detectivos (alertas y auditoría) y correctivos (revocación, restauración y respuesta a incidentes); ninguno sustituye por sí solo a los demás.

En todos los casos se debe conservar evidencia de ejecución: solicitudes HTTP, resultados de pruebas, registros de auditoría o actas de recuperación. Los niveles residuales son hipótesis de diseño; su reducción no está demostrada hasta completar el plan de pruebas.

6. Relación con MITRE ATT&CK

La matriz ATT&CK representa comportamientos del adversario, no controles defensivos. Se incluyen solo técnicas relacionadas con ataques concretos del sistema. Riesgos legales como recolección excesiva o conservación indefinida se gestionan con privacidad por diseño y no se fuerzan a ATT&CK.

ID

Técnica

Táctica

Escenario

Defensa

T1110.004

Credential Stuffing

Credential Access

R13: probar credenciales filtradas.

MFA, limitación, anomalías.

T1078

Valid Accounts

Initial Access

R04/R17: cuenta comprometida.

Revocar, roles, auditoría.

T1539

Steal Web Session Cookie

Credential Access

R04: robo de cookie de sesión.

HttpOnly, Secure, expiración.

T1199

Trusted Relationship

Initial Access

R10: abuso de canal de aseguradora.

Scopes y credenciales por socio.

T1552.001

Credentials In Files

Credential Access

R18: secretos en código/configuración.

Vault, escaneo, rotación.

T1499.003

Application Exhaustion Flood

Impact

R14: saturación de API.

Limitación, colas, monitoreo.

T1485

Data Destruction

Impact

R07: borrado intencional de datos.

Backups aislados, permisos.

T1098

Account Manipulation

Persistence

R20: cambios de privilegios.

Revisión de roles, alertas.



Tabla 6.1. Correspondencias seleccionadas, no equivalencias automáticas.

7. Plan de verificación propuesto

Prueba

Procedimiento

Resultado esperado

Evidencia

P01 / S04,S05,S14

Revisar UI y esquema de datos.

No historia clínica, religión, ingresos, geo permanente ni tarjeta.

Capturas y DDL.

P02 / S08

Aseguradora A solicita póliza B.

403/404 sin filtración; intento auditado.

Postman y logs.

P03 / S06

Dependiente sin vínculo validado.

No se crea relación de representación.

Test positivo/negativo.

P04 / S10

Reutilizar token caducado o revocado.

Acceso denegado y sesión cerrada.

Postman.

P05 / S07

Enviar petición de seguro sin firma o repetida.

Error de validación; sin doble autorización.

Contract tests.

P06 / S11

Webhook de pago falso.

No cambia estado de orden.

Logs con evento único.

P07 / S01

Acceder a cita ajena cambiando ID.

403/404 sin datos ajenos.

Tests API.

P08 / S01

100 solicitudes simultáneas a un turno.

Una sola confirmación.

JMeter + DB.

P09 / S02

Login de ensayo con credenciales erróneas.

Tasa controlada, alerta, sin revelar usuario.

Runner y métricas.

P10 / S09

Visualizar recordatorio en pantalla bloqueada.

Solo texto neutro.

Captura de prueba.

P11 / S12

Acciones de dos empleados distintos.

Trazabilidad individual de actor/fecha/objeto.

Registros.

P12 / S13

Simular caída y restaurar copia aislada.

RTO y RPO medidos y comparados con objetivo.

Acta y checksums.

P13 / S01

Probar entrada SQL/XSS en campos.

Sin ejecución ni alteración de datos.

DAST/SAST y test.

P14 / S14

Vencer plazo de retención de un dato ficticio.

Se elimina o disocia conforme política.

Job y auditoría.



Tabla 7.1. Plan de evidencia futura: ninguna prueba se declara ejecutada.

7.1 Criterios para aprobar el prototipo

No existe acceso cruzado entre pacientes, centros o aseguradoras; todas las rutas sensibles comprueban autorización por objeto.

No se almacenan historia clínica, PAN completo, CVV ni información extra prohibida en el módulo de reservas.

La confirmación de cupos y pagos es transaccional e idempotente; los errores quedan registrados.

Las pruebas de seguridad críticas y las pruebas de concurrencia se ejecutan con datos sintéticos y adjuntan evidencia.

La restauración se comprueba; los objetivos de capacidad/recuperación se revisan con métricas y no con promesas comerciales.

8. Defensa de la propuesta al cliente

Se mantiene exactamente lo que compra el paciente: encontrar un médico, obtener un turno, validar su seguro y pagar lo que corresponde. Eliminamos, en cambio, las funciones que encarecen la solución sin aportar valor a la reserva: pedir toda la historia clínica de entrada, compartir la base de pacientes entre aseguradoras, guardar tarjetas y utilizar datos para publicidad e IA de manera obligatoria.

La arquitectura propuesta reduce costo y riesgo: una sola aplicación responsiva sirve a web y móvil; los cinco conectores de seguro pueden incorporarse progresivamente; una pasarela especializada evita mantener información de tarjetas; y los permisos se conceden por paciente, establecimiento, profesional y aseguradora. Cada inversión en seguridad tiene una prueba de aceptación concreta.

El compromiso de implementación es entregar primero la reserva segura y las integraciones simuladas, medir capacidad para 2.000 usuarios simultáneos y habilitar aliados reales únicamente tras validación técnica, legal y contractual. Esta decisión permite defender el producto como viable, escalable y respetuoso de la privacidad, sin declarar que el prototipo ya fue probado o certificado.

9. Conclusiones

El modelo cumple el objetivo funcional y corrige los requerimientos inseguros S01–S14 sin solicitar definiciones al cliente. La prioridad se establece por severidad: exceso de datos, acceso interorganizacional, identidad y menores, sesiones y tarjetas, auditoría, disponibilidad e integridad de operaciones. El plan integra prevención, detección, corrección y verificación, conforme a los conceptos de la Unidad 1.

Este informe constituye una propuesta académica de diseño, no una certificación ni un dictamen legal. Su utilidad inmediata es servir de especificación para desarrollar el aplicativo y generar evidencia real de seguridad durante las pruebas.

10. Referencias

[E1] Enunciado del ejercicio práctico 5: Aplicación para solicitar consultas médicas utilizando seguros. Documento proporcionado por el docente.

[N1] Notion, Unidad 1 — Fundamentos de Seguridad Informática, temas 1.1.1–1.3.2, especialmente 1.1.4 y 1.3.1. https://app.notion.com/p/d563c2ad6c5c8324879c0126a0cfbf96

[L1] Ecuador, Ley Orgánica de Protección de Datos Personales (2021), arts. 7, 8, 10, 25 y 26. https://www.registroficial.gob.ec/267223-2/

[L2] Superintendencia de Protección de Datos Personales, Consentimiento y bases legitimadoras. https://www.spdp.gob.ec/docs/proteccion-de-datos-personales/general/consentimiento/

[L3] SPDP, criterios sobre categorías especiales de datos, incluido art. 25 LOPDP. https://www.spdp.gob.ec/docs/consultas-absueltas/2026-2/oficio-n-spdp-igrd-2026-514-o/

[T1] OWASP, API Security Top 10 2023, especialmente API1 BOLA. https://api-security.owasp.org/editions/2023/en/0x11-t10/

[T2] MITRE ATT&CK Enterprise, técnicas T1110.004, T1078, T1539, T1199, T1552.001, T1499.003, T1485 y T1098. https://attack.mitre.org/techniques/

[T3] NIST, Cybersecurity Framework 2.0 (Govern, Identify, Protect, Detect, Respond, Recover). https://www.nist.gov/cyberframework

[T4] PCI Security Standards Council, guías de protección de datos de tarjeta y datos sensibles de autenticación. https://www.pcisecuritystandards.org/

Fuentes consultadas y contrastadas: 29 de octubre de 2026.