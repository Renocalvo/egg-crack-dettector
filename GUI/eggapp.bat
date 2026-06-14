@echo off
title EggApp — Laptop PC
echo ============================================
echo   EggApp - Egg Crack Detector (Laptop PC)
echo ============================================
echo.

:: Pindah ke folder pc
cd /d "D:\Angpao\project-egg-detection\GUI\pc"

:: Aktifkan virtual environment
call venv\Scripts\activate

:: Cek apakah aktivasi berhasil
if errorlevel 1 (
    echo [ERROR] Virtual environment tidak ditemukan!
    echo Pastikan folder venv ada di C:\eggapp\pc\
    pause
    exit /b 1
)

echo [OK] Virtual environment aktif
echo [OK] Memulai EggApp Laptop...
echo.

:: Jalankan aplikasi
python pc_app.py

:: Jika error
if errorlevel 1 (
    echo.
    echo [ERROR] Aplikasi berhenti dengan error.
    pause
)