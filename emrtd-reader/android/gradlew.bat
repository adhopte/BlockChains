@rem Gradle startup script for Windows
@if "%DEBUG%"=="" @echo off
setlocal
set JAVA_EXE=java.exe
set APP_HOME=%~dp0
set CLASSPATH=%APP_HOME%gradle\wrapper\gradle-wrapper.jar
"%JAVA_EXE%" -classpath "%CLASSPATH%" org.gradle.wrapper.GradleWrapperMain %*
