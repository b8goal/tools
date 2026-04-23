//
//  TimerViewModel.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import Foundation
import Combine
import UserNotifications
import AppKit

/// Main timer view model
class TimerViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var timerMode: TimerMode = .basic
    @Published var timerState: TimerState = .idle
    @Published var timeRemaining: TimeInterval = 0
    @Published var totalTime: TimeInterval = 0
    @Published var presets: [TimerPreset] = []
    
    // Time input components
    @Published var selectedHours: Int = 0
    @Published var selectedMinutes: Int = 5
    @Published var selectedSeconds: Int = 0
    
    // Alarm sound
    @Published var selectedAlarmSound: AlarmSound = .beep
    
    // MARK: - Private Properties
    private var timer: Timer?
    private let notificationManager = NotificationManager.shared
    private let presetsKey = "SavedTimerPresets"
    private let alarmSoundKey = "SelectedAlarmSound"
    
    // MARK: - Computed Properties
    var progress: Double {
        guard totalTime > 0 else { return 0 }
        return 1.0 - (timeRemaining / totalTime)
    }
    
    var formattedTimeRemaining: String {
        let hours = Int(timeRemaining) / 3600
        let minutes = (Int(timeRemaining) % 3600) / 60
        let seconds = Int(timeRemaining) % 60
        
        if hours > 0 {
            return String(format: "%02d:%02d:%02d", hours, minutes, seconds)
        } else {
            return String(format: "%02d:%02d", minutes, seconds)
        }
    }
    
    // MARK: - Initialization
    init() {
        loadPresets()
        loadAlarmSound()
        requestNotificationPermission()
    }
    
    // MARK: - Timer Control
    func startTimer() {
        guard timerState != .running else { return }
        
        if timerState == .idle {
            // Calculate total time from input
            totalTime = TimeInterval(selectedHours * 3600 + selectedMinutes * 60 + selectedSeconds)
            timeRemaining = totalTime
            
            guard totalTime > 0 else { return }
        }
        
        timerState = .running
        
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
    }
    
    func pauseTimer() {
        guard timerState == .running else { return }
        timerState = .paused
        timer?.invalidate()
        timer = nil
    }
    
    func resetTimer() {
        timerState = .idle
        timer?.invalidate()
        timer = nil
        timeRemaining = 0
        totalTime = 0
    }
    
    private func tick() {
        guard timeRemaining > 0 else {
            timerCompleted()
            return
        }
        
        timeRemaining -= 1
    }
    
    private func timerCompleted() {
        timerState = .idle
        timer?.invalidate()
        timer = nil
        
        // Send notification
        notificationManager.sendTimerCompletedNotification()
        
        // Play selected alarm sound
        selectedAlarmSound.play()
    }
    
    // MARK: - Preset Management
    func loadPresets() {
        if let data = UserDefaults.standard.data(forKey: presetsKey),
           let decoded = try? JSONDecoder().decode([TimerPreset].self, from: data) {
            presets = decoded
        } else {
            // Load default presets
            presets = TimerPreset.defaultPresets
            savePresets()
        }
    }
    
    func savePresets() {
        if let encoded = try? JSONEncoder().encode(presets) {
            UserDefaults.standard.set(encoded, forKey: presetsKey)
        }
    }
    
    func addPreset(_ preset: TimerPreset) {
        presets.append(preset)
        savePresets()
    }
    
    func deletePreset(at offsets: IndexSet) {
        for index in offsets.sorted(by: >) {
            presets.remove(at: index)
        }
        savePresets()
    }
    
    func updatePreset(_ preset: TimerPreset) {
        if let index = presets.firstIndex(where: { $0.id == preset.id }) {
            presets[index] = preset
            savePresets()
        }
    }
    
    func applyPreset(_ preset: TimerPreset) {
        resetTimer()
        
        let hours = Int(preset.duration) / 3600
        let minutes = (Int(preset.duration) % 3600) / 60
        let seconds = Int(preset.duration) % 60
        
        selectedHours = hours
        selectedMinutes = minutes
        selectedSeconds = seconds
    }
    
    func resetToDefaultPresets() {
        presets = TimerPreset.defaultPresets
        savePresets()
    }
    
    // MARK: - Alarm Sound Management
    func loadAlarmSound() {
        if let soundString = UserDefaults.standard.string(forKey: alarmSoundKey),
           let sound = AlarmSound(rawValue: soundString) {
            selectedAlarmSound = sound
        }
    }
    
    func saveAlarmSound() {
        UserDefaults.standard.set(selectedAlarmSound.rawValue, forKey: alarmSoundKey)
    }
    
    // MARK: - Notification Permission
    private func requestNotificationPermission() {
        notificationManager.requestAuthorization()
    }
}
