//
//  NotificationManager.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import Foundation
import UserNotifications

/// Manages user notifications
class NotificationManager {
    static let shared = NotificationManager()
    
    private let notificationCenter = UNUserNotificationCenter.current()
    
    private init() {}
    
    /// Request notification authorization
    func requestAuthorization() {
        notificationCenter.requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if let error = error {
                print("Notification authorization error: \(error.localizedDescription)")
            }
            
            if granted {
                print("Notification permission granted")
            } else {
                print("Notification permission denied")
            }
        }
    }
    
    /// Send timer completed notification
    func sendTimerCompletedNotification() {
        let content = UNMutableNotificationContent()
        content.title = "Time's Up!"
        content.body = "Your timer has completed."
        content.sound = .default
        
        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil // Deliver immediately
        )
        
        notificationCenter.add(request) { error in
            if let error = error {
                print("Failed to send notification: \(error.localizedDescription)")
            }
        }
    }
}
