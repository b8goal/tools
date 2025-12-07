//
//  ColorTheme.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import SwiftUI

/// App color theme
struct ColorTheme {
    // MARK: - Primary Colors
    static let primaryGradient = LinearGradient(
        colors: [
            Color(red: 0.4, green: 0.6, blue: 1.0),
            Color(red: 0.6, green: 0.4, blue: 1.0)
        ],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
    
    static let accentColor = Color(red: 0.5, green: 0.5, blue: 1.0)
    
    // MARK: - Timer Colors
    static let timerRunning = Color.green
    static let timerPaused = Color.orange
    static let timerIdle = Color.gray
    
    // MARK: - Background Colors
    static let cardBackground = Color(nsColor: .controlBackgroundColor)
    static let appBackground = Color(nsColor: .windowBackgroundColor)
    
    // MARK: - Text Colors
    static let primaryText = Color.primary
    static let secondaryText = Color.secondary
    
    // MARK: - Visual Timer Gradient
    static func visualTimerGradient(progress: Double) -> AngularGradient {
        let colors: [Color] = progress > 0.5
            ? [.green, .yellow, .orange]
            : progress > 0.2
            ? [.yellow, .orange, .red]
            : [.orange, .red, .red]
        
        return AngularGradient(
            colors: colors,
            center: .center,
            startAngle: .degrees(0),
            endAngle: .degrees(360)
        )
    }
    
    // MARK: - Button Styles
    static let buttonGradient = LinearGradient(
        colors: [
            Color(red: 0.3, green: 0.5, blue: 0.9),
            Color(red: 0.5, green: 0.3, blue: 0.9)
        ],
        startPoint: .leading,
        endPoint: .trailing
    )
}

// MARK: - Custom Button Style
struct PremiumButtonStyle: ButtonStyle {
    var isDestructive: Bool = false
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(
                isDestructive
                    ? LinearGradient(colors: [.red, .orange], startPoint: .leading, endPoint: .trailing)
                    : ColorTheme.buttonGradient
            )
            .foregroundColor(.white)
            .cornerRadius(10)
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
            .animation(.easeInOut(duration: 0.1), value: configuration.isPressed)
    }
}

// MARK: - Custom Card Style
struct CardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding()
            .background(ColorTheme.cardBackground)
            .cornerRadius(12)
            .shadow(color: Color.black.opacity(0.1), radius: 5, x: 0, y: 2)
    }
}

extension View {
    func cardStyle() -> some View {
        modifier(CardModifier())
    }
}
