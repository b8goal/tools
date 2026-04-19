//
//  AlarmSound.swift
//  TimeTimer
//
//  Created on 2025-12-04.
//

import Foundation
import AppKit

/// Alarm sound options
enum AlarmSound: String, CaseIterable, Codable {
    // System sounds
    case beep = "Beep"
    case glass = "Glass"
    case hero = "Hero"
    case morse = "Morse"
    case ping = "Ping"
    case pop = "Pop"
    case purr = "Purr"
    case sosumi = "Sosumi"
    case submarine = "Submarine"
    case tink = "Tink"
    
    // Nature sounds
    case rain = "Rain"
    case wave = "Wave"
    case train = "Train"
    case grass = "Grass"
    
    // Modern sounds
    case digitalChime = "Digital Chime"
    case softBell = "Soft Bell"
    case ambientRise = "Ambient Rise"
    case crystal = "Crystal"
    case zenBowl = "Zen Bowl"
    
    // Trendy alarm sounds
    case gentleWake = "Gentle Wake"
    case morningBirds = "Morning Birds"
    case harp = "Harp"
    case marimba = "Marimba"
    case xylophone = "Xylophone"
    
    var displayName: String {
        return rawValue
    }
    
    var isCustomSound: Bool {
        switch self {
        case .rain, .wave, .train, .grass,
             .digitalChime, .softBell, .ambientRise, .crystal, .zenBowl,
             .gentleWake, .morningBirds, .harp, .marimba, .xylophone:
            return true
        default:
            return false
        }
    }
    
    var audioFileName: String {
        switch self {
        case .digitalChime: return "digital_chime"
        case .softBell: return "soft_bell"
        case .ambientRise: return "ambient_rise"
        case .zenBowl: return "zen_bowl"
        case .gentleWake: return "gentle_wake"
        case .morningBirds: return "morning_birds"
        default: return rawValue.lowercased()
        }
    }
    
    var systemSoundName: String {
        return rawValue
    }
    
    func play() {
        if isCustomSound {
            playCustomSound()
        } else {
            playSystemSound()
        }
    }
    
    private func playSystemSound() {
        if let sound = NSSound(named: systemSoundName) {
            sound.play()
        } else {
            NSSound.beep()
        }
    }
    
    private func playCustomSound() {
        guard let soundURL = Bundle.main.url(forResource: audioFileName, withExtension: "wav") else {
            NSSound.beep()
            return
        }
        
        // Use NSSound instead of AVAudioPlayer for macOS
        if let sound = NSSound(contentsOf: soundURL, byReference: false) {
            sound.play()
        } else {
            NSSound.beep()
        }
    }
}
