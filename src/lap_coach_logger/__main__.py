"""Entry point for ``python -m lap_coach_logger``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lap-coach-logger",
        description="Local telemetry logger for sim racing",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug-level logging"
    )
    parser.add_argument(
        "--import-lmu",
        metavar="PATH",
        help="Import an official Le Mans Ultimate DuckDB telemetry recording into a local session bundle",
    )
    parser.add_argument(
        "--export-setup-dataset",
        metavar="PATH",
        help="Export a local setup-coach dataset from saved session bundles as JSON or CSV",
    )
    parser.add_argument(
        "--analyze-setup-bundle",
        metavar="PATH",
        help="Analyze one saved session bundle and print baseline setup recommendations",
    )
    parser.add_argument(
        "--train-setup-model",
        metavar="PATH",
        help="Train and export a local setup-coach residual model as JSON",
    )
    parser.add_argument(
        "--setup-model",
        metavar="PATH",
        help="Optional residual-model JSON to refine setup-bundle analysis",
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        help="Override the output directory for import and dataset export commands",
    )
    args = parser.parse_args()

    if args.import_lmu:
        from lap_coach_logger.config.manager import ConfigManager
        from lap_coach_logger.core.lmu_import import import_lmu_recording, print_lmu_import_result

        config = ConfigManager().load()
        output_root = args.output_dir or config.output_dir
        try:
            bundle_dir = import_lmu_recording(
                args.import_lmu,
                output_root=output_root,
                config=config,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        print_lmu_import_result(bundle_dir)
        return

    if args.export_setup_dataset:
        from lap_coach_logger.config.manager import ConfigManager
        from lap_coach_logger.core.setup_coach import (
            export_setup_dataset,
            print_setup_dataset_result,
        )

        config = ConfigManager().load()
        output_root = args.output_dir or config.output_dir
        try:
            dataset = export_setup_dataset(
                output_root=output_root,
                export_path=args.export_setup_dataset,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        print_setup_dataset_result(dataset, args.export_setup_dataset)
        return

    if args.analyze_setup_bundle:
        from lap_coach_logger.core.setup_coach import (
            analyze_setup_bundle,
            print_setup_bundle_analysis_result,
        )
        from lap_coach_logger.core.setup_residual_model import (
            load_residual_model,
            refine_bundle_snapshot,
        )

        try:
            snapshot = analyze_setup_bundle(args.analyze_setup_bundle)
            if args.setup_model:
                model = load_residual_model(args.setup_model)
                snapshot, _ = refine_bundle_snapshot(snapshot, args.analyze_setup_bundle, model)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        print_setup_bundle_analysis_result(snapshot, args.analyze_setup_bundle)
        return

    if args.train_setup_model:
        from lap_coach_logger.config.manager import ConfigManager
        from lap_coach_logger.core.setup_residual_model import (
            print_residual_model_result,
            train_residual_model,
        )

        config = ConfigManager().load()
        output_root = args.output_dir or config.output_dir
        try:
            artifact = train_residual_model(
                output_root=output_root,
                export_path=args.train_setup_model,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        print_residual_model_result(artifact, args.train_setup_model)
        return

    from lap_coach_logger.bootstrap import run

    run(debug_override=args.debug)


if __name__ == "__main__":
    main()
