//
//  BasicTimerView.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import SwiftUI

/// Basic countdown timer view
struct BasicTimerView: View {
    @ObservedObject var viewModel: TimerViewModel
    
    var body: some View {
        VStack(spacing: 20) {
            // Large time display
            Text(viewModel.formattedTimeRemaining)
                .font(.system(size: 72, weight: .thin, design: .rounded))
                .foregroundColor(timerColor)
                .monospacedDigit()
                .animation(.easeInOut, value: viewModel.timeRemaining)
            
            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    // Background
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color.gray.opacity(0.2))
                        .frame(height: 20)
                    
                    // Progress
                    RoundedRectangle(cornerRadius: 10)
                        .fill(progressGradient)
                        .frame(width: geometry.size.width * viewModel.progress, height: 20)
                        .animation(.linear(duration: 1.0), value: viewModel.progress)
                }
            }
            .frame(height: 20)
            .padding(.horizontal)
            
            // Status text
            Text(statusText)
                .font(.headline)
                .foregroundColor(.secondary)
        }
        .padding()
    }
    
    private var timerColor: Color {
        switch viewModel.timerState {
        case .running:
            return ColorTheme.timerRunning
        case .paused:
            return ColorTheme.timerPaused
        case .idle:
            return ColorTheme.timerIdle
        }
    }
    
    private var progressGradient: LinearGradient {
        let progress = viewModel.progress
        
        if progress < 0.3 {
            return LinearGradient(
                colors: [.green, .green],
                startPoint: .leading,
                endPoint: .trailing
            )
        } else if progress < 0.7 {
            return LinearGradient(
                colors: [.green, .yellow],
                startPoint: .leading,
                endPoint: .trailing
            )
        } else {
            return LinearGradient(
                colors: [.yellow, .orange, .red],
                startPoint: .leading,
                endPoint: .trailing
            )
        }
    }
    
    private var statusText: String {
        switch viewModel.timerState {
        case .running:
            return "Running..."
        case .paused:
            return "Paused"
        case .idle:
            return "Ready"
        }
    }
}
