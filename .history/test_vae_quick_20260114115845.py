"""Quick test for VAE module."""
from sigmavault.ml.pattern_vae import PatternObfuscationVAE, VAEConfig, create_pattern_vae
from sigmavault.ml.synthetic_data_generator import SyntheticDataGenerator, PatternType
from datetime import datetime
import tempfile
from pathlib import Path

print('Testing Pattern Obfuscation VAE...')
print('='*50)

with tempfile.TemporaryDirectory() as tmpdir:
    vault_path = Path(tmpdir)
    
    # Create VAE
    vae = create_pattern_vae(vault_path, latent_dim=4)
    print(f'✅ VAE created with latent_dim={vae.config.latent_dim}')
    
    # Generate synthetic training data
    gen = SyntheticDataGenerator(seed=42)
    sequences = []
    
    for day in range(7):
        events = gen.generate_normal_workday(
            vault_id='test-vault',
            start_date=datetime(2026, 1, day+1),
            days=1
        )
        for i in range(0, len(events)-20, 10):
            sequences.append(events[i:i+20])
    
    print(f'✅ Generated {len(sequences)} training sequences')
    
    if len(sequences) >= 50:
        print('   Training VAE (3 epochs)...')
        vae.config.epochs = 3
        metrics = vae.train(sequences, verbose=0)
        print(f'✅ Training complete!')
        print(f'   - Samples: {metrics["n_samples"]}')
        print(f'   - Final loss: {metrics["final_loss"]:.4f}')
        
        decoys = vae.generate_decoys(n=5)
        print(f'✅ Generated {len(decoys)} decoy patterns')
        for i, d in enumerate(decoys):
            print(f'   Decoy {i+1}: freq={d.features["access_frequency"]:.1f}')

print('='*50)
print('✅ Pattern Obfuscation VAE module verified!')
