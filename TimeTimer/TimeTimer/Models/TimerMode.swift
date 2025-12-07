//
//  TimerMode.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import Foundation

/// Timer display mode
enum TimerMode: String, CaseIterable, Codable {
    case basic = "Basic"
    case visual = "Visual"
    
    var displayName: String {
        return self.rawValue
    }
}

/// Timer state
enum TimerState {
    case idle
    case running
    case paused
}
