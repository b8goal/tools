//
//  TimerPreset.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import Foundation

/// Timer preset model
struct TimerPreset: Identifiable, Codable, Equatable {
    let id: UUID
    var name: String
    var duration: TimeInterval // in seconds
    
    init(id: UUID = UUID(), name: String, duration: TimeInterval) {
        self.id = id
        self.name = name
        self.duration = duration
    }
    
    /// Formatted duration string (MM:SS or HH:MM:SS)
    var formattedDuration: String {
        let hours = Int(duration) / 3600
        let minutes = (Int(duration) % 3600) / 60
        let seconds = Int(duration) % 60
        
        if hours > 0 {
            return String(format: "%02d:%02d:%02d", hours, minutes, seconds)
        } else {
            return String(format: "%02d:%02d", minutes, seconds)
        }
    }
    
    /// Default presets
    static let defaultPresets: [TimerPreset] = [
        TimerPreset(name: "5 min", duration: 5 * 60),
        TimerPreset(name: "10 min", duration: 10 * 60),
        TimerPreset(name: "15 min", duration: 15 * 60),
        TimerPreset(name: "25 min (Pomodoro)", duration: 25 * 60),
        TimerPreset(name: "30 min", duration: 30 * 60),
        TimerPreset(name: "45 min", duration: 45 * 60),
        TimerPreset(name: "1 hour", duration: 60 * 60)
    ]
}
