# language: en
@test_regresion @perfil_admin
Feature: Login en la aplicación
  Como usuario de la aplicación
  Quiero iniciar sesión con mi usuario y contraseña
  Para acceder a las funcionalidades del sistema

  @smoke
  Scenario: Inicio de sesión exitoso
    Given que el usuario está autenticado
    Then la sesión queda iniciada
