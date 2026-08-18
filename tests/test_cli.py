"""Unit tests for unified gmaps-mcp CLI."""

import pytest
from unittest.mock import AsyncMock, patch

from gmaps_mcp.cli import async_main, build_parser
from gmaps_mcp.schemas import GetPlaceDetailsResult, Place, SearchGoogleMapsResult


def test_cli_parser_build():
    parser = build_parser()

    # Test search args
    args = parser.parse_args(["search", "bakeries", "Paris", "--limit", "25", "--grid", "--country", "fr", "--format", "json"])
    assert args.command == "search"
    assert args.term == "bakeries"
    assert args.location == "Paris"
    assert args.limit == 25
    assert args.grid is True
    assert args.country == "fr"
    assert args.format == "json"

    # Test details args
    args_det = parser.parse_args(["details", "ChIJ123456", "--country", "us", "--format", "table"])
    assert args_det.command == "details"
    assert args_det.place == "ChIJ123456"
    assert args_det.country == "us"

    # Test serve args
    args_srv = parser.parse_args(["serve", "--transport", "streamable-http", "--port", "9000"])
    assert args_srv.command == "serve"
    assert args_srv.transport == "streamable-http"
    assert args_srv.port == 9000


@pytest.mark.asyncio
async def test_cli_search_command_output(capsys):
    parser = build_parser()
    args = parser.parse_args(["search", "coffee", "Paris", "--country", "fr", "--format", "table"])

    sample_res = SearchGoogleMapsResult(
        term="coffee",
        location="Paris",
        query="coffee in Paris",
        country="fr",
        language="en",
        total_results=1,
        delivery_mode="inline",
        places=[
            Place(
                place_id="ChIJ_PARIS_1",
                name="Cafe de Paris",
                category="Cafe",
                address="10 Rue Paris",
                phone="01 23 45 67 89",
                international_phone="+33 1 23 45 67 89",
                rating=4.7,
                review_count=150,
            )
        ],
    )

    with patch("gmaps_mcp.cli.search_google_maps", new=AsyncMock(return_value=sample_res)):
        await async_main(args)
        captured = capsys.readouterr()
        assert "Cafe de Paris" in captured.out
        assert "01 23 45 67 89" in captured.out


@pytest.mark.asyncio
async def test_cli_details_command_output(capsys):
    parser = build_parser()
    args = parser.parse_args(["details", "Eiffel Tower", "--format", "table"])

    sample_det = GetPlaceDetailsResult(
        place=Place(
            place_id="ChIJ_DETAILS_1",
            name="Eiffel Tower",
            category="Tourist attraction",
            address="Champ de Mars, 5 Av. Anatole France, 75007 Paris",
            rating=4.7,
            review_count=350000,
        ),
        found=True,
        query_or_id="Eiffel Tower",
    )

    with patch("gmaps_mcp.cli.get_place_details", new=AsyncMock(return_value=sample_det)):
        await async_main(args)
        captured = capsys.readouterr()
        assert "Eiffel Tower" in captured.out
        assert "Tourist attraction" in captured.out


@pytest.mark.asyncio
async def test_cli_details_command_json_and_csv(capsys, tmp_path):
    parser = build_parser()
    sample_det = GetPlaceDetailsResult(
        place=Place(
            place_id="ChIJ_DETAILS_1",
            name="Eiffel Tower",
            category="Tourist attraction",
            address="Champ de Mars, Paris",
            phone="01 23 45 67 89",
            rating=4.7,
            review_count=350000,
        ),
        found=True,
        query_or_id="Eiffel Tower",
    )

    with patch("gmaps_mcp.cli.get_place_details", new=AsyncMock(return_value=sample_det)):
        # Test JSON format
        args_json = parser.parse_args(["details", "Eiffel Tower", "--format", "json"])
        await async_main(args_json)
        out_json = capsys.readouterr().out
        assert '"name": "Eiffel Tower"' in out_json

        # Test CSV format
        args_csv = parser.parse_args(["details", "Eiffel Tower", "--format", "csv"])
        await async_main(args_csv)
        out_csv = capsys.readouterr().out
        assert "place_id,name,category" in out_csv
        assert "Eiffel Tower" in out_csv

        # Test export to CSV file
        csv_file = str(tmp_path / "details.csv")
        args_out = parser.parse_args(["details", "Eiffel Tower", "--output", csv_file])
        await async_main(args_out)
        assert (tmp_path / "details.csv").exists()

        # Test export to JSON file
        json_file = str(tmp_path / "details.json")
        args_json_out = parser.parse_args(["details", "Eiffel Tower", "--output", json_file])
        await async_main(args_json_out)
        assert (tmp_path / "details.json").exists()


@pytest.mark.asyncio
async def test_cli_details_not_found(capsys):
    parser = build_parser()
    sample_not_found = GetPlaceDetailsResult(
        place=None,
        found=False,
        query_or_id="NonExistentPlace12345",
    )

    with patch("gmaps_mcp.cli.get_place_details", new=AsyncMock(return_value=sample_not_found)):
        args = parser.parse_args(["details", "NonExistentPlace12345"])
        await async_main(args)
        captured = capsys.readouterr()
        assert "Place not found" in captured.out

