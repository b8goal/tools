//
//  ContentView.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import SwiftUI

/// Main content view
struct ContentView: View {
    @StateObject private var viewModel = TimerViewModel()
    @ObservedObject var windowManager: WindowManager
    @State private var showingPresetManagement = false
    @State private var showQuickPresets = true
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView
                .padding()
            
            Divider()
            
            ScrollView {
                VStack(spacing: 30) {
                    // Timer mode selector
                    timerModeSelector
                        .padding(.top)
                    
                    // Timer display
                    timerDisplayView
                        .cardStyle()
                        .padding(.horizontal)
                    
                    // Time input (only when idle)
                    if viewModel.timerState == .idle {
                        timeInputView
                            .cardStyle()
                            .padding(.horizontal)
                    }
                    
                    // Presets (conditional)
                    if showQuickPresets {
                        presetsView
                            .cardStyle()
                            .padding(.horizontal)
                    }
                    
                    // Control buttons
                    controlButtonsView
                        .padding()
                }
                .padding(.bottom)
            }
        }
        .frame(minWidth: 600, minHeight: 700)
        .background(ColorTheme.appBackground)
    }
    
    // MARK: - Header
    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Time Timer")
                    .font(.system(size: 32, weight: .bold, design: .rounded))
                    .foregroundStyle(ColorTheme.primaryGradient)
                
                Text("Focus & Productivity")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Alarm sound picker with preview
            HStack(spacing: 6) {
                Image(systemName: "speaker.wave.2.fill")
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
                
                Picker("Alarm", selection: $viewModel.selectedAlarmSound) {
                    ForEach(AlarmSound.allCases, id: \.self) { sound in
                        Text(sound.displayName).tag(sound)
                    }
                }
                .pickerStyle(.menu)
                .frame(width: 100)
                .onChange(of: viewModel.selectedAlarmSound) { newSound in
                    viewModel.saveAlarmSound()
                    // Play preview
                    newSound.play()
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.secondary.opacity(0.1))
            .cornerRadius(8)
            .help("Select alarm sound (plays preview)")
            
            // Quick Presets toggle button
            Button(action: {
                showQuickPresets.toggle()
            }) {
                HStack(spacing: 6) {
                    Image(systemName: showQuickPresets ? "list.bullet.circle.fill" : "list.bullet.circle")
                        .font(.system(size: 16))
                    Text("Presets")
                        .font(.system(size: 13))
                }
                .foregroundColor(showQuickPresets ? .blue : .secondary)
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(showQuickPresets ? Color.blue.opacity(0.1) : Color.secondary.opacity(0.05))
            .cornerRadius(8)
            .help("Toggle quick presets")
            
            // Always on Top toggle button
            Button(action: {
                windowManager.isAlwaysOnTop.toggle()
            }) {
                HStack(spacing: 6) {
                    Image(systemName: windowManager.isAlwaysOnTop ? "pin.fill" : "pin")
                        .font(.system(size: 16))
                    Text("Pin")
                        .font(.system(size: 13))
                }
                .foregroundColor(windowManager.isAlwaysOnTop ? .blue : .secondary)
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(windowManager.isAlwaysOnTop ? Color.blue.opacity(0.1) : Color.secondary.opacity(0.05))
            .cornerRadius(8)
            .help("Pin window on top")
            
            // Settings button
            Button(action: {
                showingPresetManagement = true
            }) {
                Image(systemName: "gearshape.fill")
                    .font(.system(size: 18))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
            .padding(8)
            .background(Color.secondary.opacity(0.05))
            .cornerRadius(8)
            .help("Manage Presets")
        }
        .sheet(isPresented: $showingPresetManagement) {
            PresetManagementView(viewModel: viewModel)
        }
    }
    
    // MARK: - Timer Mode Selector
    private var timerModeSelector: some View {
        Picker("Timer Mode", selection: $viewModel.timerMode) {
            ForEach(TimerMode.allCases, id: \.self) { mode in
                Text(mode.displayName).tag(mode)
            }
        }
        .pickerStyle(.segmented)
        .frame(maxWidth: 300)
        .disabled(viewModel.timerState != .idle)
    }
    
    // MARK: - Timer Display
    @ViewBuilder
    private var timerDisplayView: some View {
        switch viewModel.timerMode {
        case .basic:
            BasicTimerView(viewModel: viewModel)
        case .visual:
            VisualTimerView(viewModel: viewModel)
        }
    }
    
    // MARK: - Time Input
    private var timeInputView: some View {
        VStack(spacing: 12) {
            Text("Set Time")
                .font(.headline)
            
            HStack(spacing: 20) {
                timePickerComponent(
                    title: "Hours",
                    selection: $viewModel.selectedHours,
                    range: 0..<24
                )
                
                Text(":")
                    .font(.title)
                    .foregroundColor(.secondary)
                
                timePickerComponent(
                    title: "Minutes",
                    selection: $viewModel.selectedMinutes,
                    range: 0..<60
                )
                
                Text(":")
                    .font(.title)
                    .foregroundColor(.secondary)
                
                timePickerComponent(
                    title: "Seconds",
                    selection: $viewModel.selectedSeconds,
                    range: 0..<60
                )
            }
        }
        .padding()
    }
    
    private func timePickerComponent(title: String, selection: Binding<Int>, range: Range<Int>) -> some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
            
            HStack(spacing: 4) {
                Button(action: {
                    if selection.wrappedValue > range.lowerBound {
                        selection.wrappedValue -= 1
                    }
                }) {
                    Image(systemName: "minus.circle.fill")
                        .font(.title3)
                }
                .buttonStyle(.plain)
                
                Text(String(format: "%02d", selection.wrappedValue))
                    .font(.title2)
                    .fontWeight(.medium)
                    .frame(width: 50)
                    .padding(.vertical, 4)
                    .background(Color.secondary.opacity(0.1))
                    .cornerRadius(6)
                
                Button(action: {
                    if selection.wrappedValue < range.upperBound - 1 {
                        selection.wrappedValue += 1
                    }
                }) {
                    Image(systemName: "plus.circle.fill")
                        .font(.title3)
                }
                .buttonStyle(.plain)
            }
        }
    }
    
    // MARK: - Presets
    private var presetsView: some View {
        VStack(spacing: 12) {
            HStack {
                Text("Quick Presets")
                    .font(.headline)
                
                Spacer()
                
                Button(action: {
                    showingPresetManagement = true
                }) {
                    Label("Manage", systemImage: "slider.horizontal.3")
                        .font(.caption)
                }
                .buttonStyle(.plain)
                .foregroundColor(.blue)
            }
            
            LazyVGrid(columns: [
                GridItem(.adaptive(minimum: 120), spacing: 12)
            ], spacing: 12) {
                ForEach(viewModel.presets.prefix(8)) { preset in
                    presetButton(preset)
                }
            }
        }
        .padding()
    }
    
    private func presetButton(_ preset: TimerPreset) -> some View {
        Button(action: {
            viewModel.applyPreset(preset)
        }) {
            VStack(spacing: 4) {
                Text(preset.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(1)
                
                Text(preset.formattedDuration)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .padding(.horizontal, 8)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.accentColor.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.accentColor.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .disabled(viewModel.timerState != .idle)
    }
    
    // MARK: - Control Buttons
    private var controlButtonsView: some View {
        HStack(spacing: 16) {
            if viewModel.timerState == .idle {
                Button(action: {
                    viewModel.startTimer()
                }) {
                    Label("Start", systemImage: "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PremiumButtonStyle())
                .disabled(viewModel.selectedHours == 0 && viewModel.selectedMinutes == 0 && viewModel.selectedSeconds == 0)
            } else if viewModel.timerState == .running {
                Button(action: {
                    viewModel.pauseTimer()
                }) {
                    Label("Pause", systemImage: "pause.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PremiumButtonStyle())
            } else if viewModel.timerState == .paused {
                Button(action: {
                    viewModel.startTimer()
                }) {
                    Label("Resume", systemImage: "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PremiumButtonStyle())
            }
            
            if viewModel.timerState != .idle {
                Button(action: {
                    viewModel.resetTimer()
                }) {
                    Label("Reset", systemImage: "arrow.counterclockwise")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PremiumButtonStyle(isDestructive: true))
            }
        }
        .frame(maxWidth: 400)
    }
}

#Preview {
    ContentView(windowManager: WindowManager())
}
