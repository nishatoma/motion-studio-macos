"""Safe Manim renderer for validated JSON animation plans."""
from __future__ import annotations

import json
import os
from pathlib import Path

from manim import *
from manim import config

# Manim imports this file to discover GeneratedScene, so apply these values at
# module scope instead of under __main__ (which is not executed by its CLI).
config.pixel_width = int(os.environ.get("MOTION_STUDIO_WIDTH", "1280"))
config.pixel_height = int(os.environ.get("MOTION_STUDIO_HEIGHT", "720"))
config.frame_rate = int(os.environ.get("MOTION_STUDIO_FPS", "24"))
config.disable_caching = True


def color(value: str):
    return ManimColor(value)


def make_face_marker(point, radius, tint):
    head = Circle(radius=radius, color=tint, fill_color=tint, fill_opacity=1).move_to(point)
    eye_l = Dot(point + LEFT * radius * 0.32 + UP * radius * 0.15, radius=radius * 0.07, color="#07131F")
    eye_r = Dot(point + RIGHT * radius * 0.32 + UP * radius * 0.15, radius=radius * 0.07, color="#07131F")
    mouth = Arc(radius=radius * 0.3, start_angle=PI + 0.25, angle=PI - 0.5, color="#07131F", stroke_width=2).move_to(point + DOWN * radius * 0.15)
    return VGroup(head, eye_l, eye_r, mouth)


def make_item(item):
    kind = item["type"]
    tint = color(item["color"])
    x, y = item["position"]
    point = np.array([x, y, 0])
    if kind in {"title", "text", "number"}:
        mob = Text(item["text"], font="Arial", font_size=item["size"], color=tint, weight="BOLD" if kind == "title" else "NORMAL")
        return mob.move_to(point)
    if kind == "line":
        w, h = item["size"]
        return Line(point + LEFT * w / 2 + DOWN * h / 2, point + RIGHT * w / 2 + UP * h / 2, color=tint, stroke_width=5)
    if kind == "circle":
        w, _ = item["size"]
        return Circle(radius=max(0.1, w / 2), color=tint, stroke_width=5).move_to(point)
    if kind == "rectangle":
        w, h = item["size"]
        return RoundedRectangle(width=w, height=h, corner_radius=0.15, color=tint, stroke_width=4).move_to(point)
    if kind == "face_marker":
        return make_face_marker(point, item["size"], tint)
    if kind == "graph":
        width, height = item["size"]
        axes = Axes(x_range=[0, 10, 2], y_range=[0, 10, 2], x_length=width, y_length=height,
                    axis_config={"color": GREY_B, "stroke_width": 2, "include_ticks": False},
                    tips=False).move_to(point)
        if item["curve"] == "linear":
            fn = lambda t: 0.8 * t
        elif item["curve"] == "logarithmic":
            fn = lambda t: 2.3 * np.log1p(t)
        else:
            fn = lambda t: min(9.5, 0.08 * np.exp(0.48 * t))
        curve = axes.plot(fn, x_range=[0, 10], color=tint, stroke_width=6)
        x_label = Text(item["x_label"], font="Arial", font_size=20, color=WHITE).next_to(axes.x_axis, DOWN, buff=0.25)
        y_label = Text(item["y_label"], font="Arial", font_size=20, color=WHITE).rotate(PI / 2).next_to(axes.y_axis, LEFT, buff=0.25)
        group = VGroup(axes, curve, x_label, y_label)
        if item.get("marker"):
            marker = make_face_marker(axes.c2p(0, fn(0)), 0.27, GOLD)
            return group, marker, curve
        return group, None, None
    raise ValueError(f"Unknown validated item type: {kind}")


def monthly_rate_for_target(monthly, years, target):
    """Solve the ordinary monthly annuity equation for the illustrative curve."""
    months = 12 * years
    low, high = 0.0, 0.1
    while monthly * np.expm1(months * np.log1p(high)) / high < target and high < 0.8:
        high *= 2
    for _ in range(90):
        rate = (low + high) / 2
        balance = monthly * np.expm1(months * np.log1p(rate)) / rate
        if balance < target:
            low = rate
        else:
            high = rate
    return (low + high) / 2


def growth_balance(monthly, start_age, age, rate):
    months = 12 * (age - start_age)
    return monthly * np.expm1(months * np.log1p(rate)) / rate


def crossing_age(monthly, start_age, end_age, rate, value):
    low, high = float(start_age), float(end_age)
    for _ in range(55):
        middle = (low + high) / 2
        if growth_balance(monthly, start_age, middle, rate) < value:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def fitted_text(value, size, tint, width, bold=False):
    label = Text(value, font="Arial", font_size=size, color=tint,
                 weight="BOLD" if bold else "NORMAL")
    if label.width > width:
        label.scale_to_fit_width(width)
    return label


def storyboard_card(value, x, y, width, height, tint, font_size=30):
    frame = RoundedRectangle(width=width, height=height, corner_radius=0.16,
                             color=tint, stroke_width=2, fill_color=tint,
                             fill_opacity=0.09).move_to([x, y, 0])
    label = fitted_text(value, font_size, "#F4F9FB", width - 0.28, bold=True).move_to(frame)
    return VGroup(frame, label)


class GeneratedScene(Scene):
    def construct(self):
        spec_file = Path(os.environ["MOTION_STUDIO_SPEC"])
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        if not config.transparent:
            self.camera.background_color = color("#0C1019")
        if spec.get("template") == "financial_stages":
            self.financial_stages()
            return
        if spec.get("template") == "portfolio_growth":
            self.portfolio_growth(spec)
            return
        if spec.get("template") == "storyboard":
            self.storyboard(spec)
            return
        visible = VGroup()
        for beat in spec["beats"]:
            if beat.get("clear_before") and len(visible):
                self.play(FadeOut(visible), run_time=0.35)
                visible = VGroup()
            animations = []
            new_items = VGroup()
            for data in beat["items"]:
                built = make_item(data)
                if data["type"] == "graph":
                    mob, marker, path = built
                else:
                    mob, marker, path = built, None, None
                new_items.add(mob)
                if data["type"] in {"line", "circle", "rectangle", "graph"}:
                    animations.append(Create(mob))
                else:
                    animations.append(FadeIn(mob, shift=UP * 0.12))
                if marker is not None:
                    new_items.add(marker)
                    animations.append(Succession(
                        FadeIn(marker, run_time=0.12),
                        MoveAlongPath(marker, path, rate_func=smooth),
                    ))
            if animations:
                self.play(AnimationGroup(*animations, lag_ratio=0), run_time=beat["duration"], rate_func=smooth)
                visible.add(*new_items)
            else:
                self.wait(beat["duration"])
        self.wait(0.4)

    def storyboard(self, spec):
        palette = {"aqua": "#55EDE3", "gold": "#FFB56B",
                   "coral": "#FF7972", "violet": "#B9A0FF"}
        previous = VGroup()
        for index, scene in enumerate(spec["scenes"]):
            if index:
                self.play(FadeOut(previous, shift=LEFT * 0.2), run_time=0.35)
            tint = palette[scene["accent"]]
            body = self.storyboard_body(scene, tint)
            if scene["layout"] == "statement":
                title = fitted_text(scene["title"], 60, tint, 11.5, True).move_to([0, 0.35, 0])
                subtitle = fitted_text(scene["subtitle"], 28, "#9CB6C3", 10.5).move_to([0, -1.15, 0])
            else:
                title = fitted_text(scene["title"], 42, "#F4F9FB", 11.9, True).move_to([0, 3.12, 0])
                subtitle = fitted_text(scene["subtitle"], 24, "#9CB6C3", 11.3).move_to([0, 2.46, 0])
            rule = Line([-0.7, 2.08, 0], [0.7, 2.08, 0], color=tint, stroke_width=4)
            visible = VGroup(title, subtitle, *body)
            if scene["layout"] != "statement":
                visible.add(rule)
            self.play(FadeIn(title, shift=UP * 0.1), FadeIn(subtitle),
                      *([Create(rule)] if scene["layout"] != "statement" else []), run_time=0.5)
            if len(body):
                self.play(AnimationGroup(*(FadeIn(item, shift=UP * 0.16) for item in body),
                                         lag_ratio=0.17), run_time=1.35)
            self.wait(max(0.25, scene["duration"] - 1.85))
            previous = visible

    def storyboard_body(self, scene, tint):
        layout, labels = scene["layout"], scene["labels"]
        items = VGroup()
        if layout == "statement":
            halo = Circle(radius=2.25, color=tint, stroke_width=2, stroke_opacity=0.35,
                          fill_color=tint, fill_opacity=0.04).move_to([0, 0.2, 0])
            items.add(halo)
        elif layout == "comparison":
            for x, label in zip([-3.15, 3.15], labels):
                card = storyboard_card(label, x, -0.35, 5.2, 3.45, tint, 40)
                stripe = Line([x - 1.5, -1.18, 0], [x + 1.5, -1.18, 0], color=tint, stroke_width=3)
                items.add(VGroup(card, stripe))
            items.add(fitted_text("VS", 28, tint, 0.9, True).move_to([0, -0.35, 0]))
        elif layout == "flow":
            xs = np.linspace(-5.0, 5.0, len(labels))
            width = min(3.25, 10.4 / len(labels) - 0.3)
            for n, (x, label) in enumerate(zip(xs, labels)):
                items.add(storyboard_card(label, float(x), -0.25, width, 1.55, tint, 27))
                if n < len(labels) - 1:
                    left = x + width / 2 + 0.1
                    right = xs[n + 1] - width / 2 - 0.1
                    items.add(Arrow([left, -0.25, 0], [right, -0.25, 0],
                                    color=tint, buff=0, stroke_width=3, max_tip_length_to_length_ratio=0.22))
        elif layout == "timeline":
            xs = np.linspace(-5.15, 5.15, len(labels))
            items.add(Line([-5.4, -0.25, 0], [5.4, -0.25, 0], color=tint, stroke_width=4))
            for n, (x, label) in enumerate(zip(xs, labels)):
                y = 0.74 if n % 2 == 0 else -1.3
                dot = Dot([x, -0.25, 0], radius=0.12, color=tint)
                text = fitted_text(label, 26, "#F4F9FB", 2.0, True).move_to([x, y, 0])
                connector = Line([x, -0.25, 0], [x, y - 0.24 if y > 0 else y + 0.24, 0],
                                 color="#406276", stroke_width=2)
                items.add(VGroup(connector, dot, text))
        elif layout == "cycle":
            count = len(labels)
            points = [np.array([3.2 * np.cos(PI / 2 - 2 * PI * n / count),
                                -0.35 + 1.75 * np.sin(PI / 2 - 2 * PI * n / count), 0])
                      for n in range(count)]
            for n, point in enumerate(points):
                items.add(storyboard_card(labels[n], point[0], point[1], 2.25, 0.78, tint, 24))
                next_point = points[(n + 1) % count]
                direction = next_point - point
                start = point + direction / np.linalg.norm(direction) * 1.18
                end = next_point - direction / np.linalg.norm(direction) * 1.18
                if np.linalg.norm(end - start) > 0.15:
                    items.add(Arrow(start, end, color=tint, buff=0, stroke_width=2.5,
                                    max_tip_length_to_length_ratio=0.18))
        elif layout == "layers":
            for n, label in enumerate(labels):
                y = 1.35 - 0.79 * n
                items.add(storyboard_card(label, 0, y, 8.6 - 0.32 * n, 0.66, tint, 26))
        elif layout == "network":
            links, cards = VGroup(), VGroup()
            for n, label in enumerate(labels):
                angle = PI / 2 - 2 * PI * n / len(labels)
                x, y = 4.0 * np.cos(angle), -0.35 + 1.7 * np.sin(angle)
                links.add(Line([0, -0.35, 0], [x, y, 0], color="#406276", stroke_width=2))
                cards.add(storyboard_card(label, x, y, 2.3, 0.7, tint, 22))
            items.add(links, storyboard_card(scene["title"], 0, -0.35, 3.2, 1.0, tint, 25), *cards)
        return items

    def financial_stages(self):
        """Four immobile cards; the arrow alone searches for the current stage."""
        shades = ["#FF6C61", "#F8C85D", "#50D8CA", "#AC8AF5"]
        rows = [2.65, 0.88, -0.89, -2.66]
        cards = VGroup()
        for index, (shade, y) in enumerate(zip(shades, rows), start=1):
            card = RoundedRectangle(width=6.8, height=1.32, corner_radius=0.22,
                                    fill_color=shade, fill_opacity=1,
                                    stroke_color="#D9F2F2", stroke_width=2).move_to([1.55, y, 0])
            label = fitted_text(f"STAGE {index}", 52, "#102331", 6.2, True).move_to(card)
            cards.add(VGroup(card, label))

        outline = RoundedRectangle(width=6.96, height=1.48, corner_radius=0.27,
                                   fill_opacity=0, stroke_color="#FFF3D4", stroke_width=5)
        outline.move_to(cards[0])
        arrow = Arrow([-6.1, rows[0], 0], [-2.08, rows[0], 0], buff=0,
                      color=WHITE, stroke_width=8, max_tip_length_to_length_ratio=0.14)
        self.play(FadeIn(cards), FadeIn(outline), FadeIn(arrow), run_time=0.35)
        self.wait(0.25)
        for index in range(1, 4):
            delta = rows[index] - rows[index - 1]
            self.play(arrow.animate.shift(UP * delta), outline.animate.shift(UP * delta),
                      run_time=0.45, rate_func=smooth)
            self.wait(0.25)
        # Finish unresolved, between Stages 2 and 3, for the narration's "unaware" beat.
        midpoint = (rows[1] + rows[2]) / 2
        self.play(arrow.animate.shift(UP * (midpoint - rows[3])), FadeOut(outline),
                  run_time=0.65, rate_func=smooth)
        self.wait(0.55)

    def portfolio_growth(self, spec):
        monthly = spec["monthly"]
        start, end = spec["start_age"], spec["end_age"]
        milestones = spec["milestones"]
        target = milestones[-1]["value"]
        rate = monthly_rate_for_target(monthly, end - start, target)
        annual = 100 * ((1 + rate) ** 12 - 1)
        balance = lambda age: growth_balance(monthly, start, age, rate)
        aqua, gold, white, muted = "#55EDE3", "#FFB56B", "#F4F9FB", "#92AFBD"

        title = Text(f"${monthly:,.0f} / MONTH", font="Arial", font_size=42,
                     weight="BOLD", color=gold).move_to([-5.95, 3.1, 0], aligned_edge=LEFT)
        title.scale_to_fit_width(min(title.width, 6.6))
        subtitle = Text(f"AGE {start} TO {end}", font="Arial", font_size=23,
                        color=muted).move_to([1.35, 3.1, 0])
        axes = Axes(x_range=[start, end, 5], y_range=[0, target * 1.06, target / 4],
                    x_length=7.8, y_length=4.25,
                    axis_config={"color": "#4D6977", "stroke_width": 2, "include_ticks": False},
                    tips=False).move_to([-1.4, -0.42, 0])
        labels = VGroup(
            Text("PORTFOLIO VALUE", font="Arial", font_size=20, color=muted).move_to([-4.55, 2.15, 0]),
            Text(str(start), font="Arial", font_size=20, color=muted).move_to([-5.3, -2.9, 0]),
            Text("AGE", font="Arial", font_size=19, color=muted).move_to([-1.4, -2.9, 0]),
            Text(str(end), font="Arial", font_size=20, color=muted).move_to([2.5, -2.9, 0]),
        )
        divider = Line([3.0, -2.45, 0], [3.0, 2.35, 0], color="#244456", stroke_width=2)
        panel_title = Text("MILESTONES", font="Arial", font_size=22, color=muted).move_to([4.6, 2.15, 0])
        footnote = Text(f"Illustrative growth  ·  {annual:.1f}% annual return implied by the final value",
                        font="Arial", font_size=18, color=muted).move_to([0, -3.52, 0])
        footnote.scale_to_fit_width(min(footnote.width, 12.4))
        self.play(FadeIn(title), FadeIn(subtitle), FadeIn(axes), FadeIn(labels),
                  FadeIn(divider), FadeIn(panel_title), FadeIn(footnote), run_time=0.85)

        marker = make_face_marker(axes.c2p(start, 0), 0.18, gold)
        if spec["marker"]:
            self.add(marker)
        previous_age = start
        for index, milestone in enumerate(milestones):
            value = milestone["value"]
            age = crossing_age(monthly, start, end, rate, value)
            path = axes.plot(balance, x_range=[previous_age, age], color=aqua,
                             stroke_width=6, use_smoothing=False)
            travel = [Create(path)]
            if spec["marker"]:
                travel.append(MoveAlongPath(marker, path, rate_func=linear))
            self.play(*travel, run_time=1.45, rate_func=linear)
            point = Dot(axes.c2p(age, value), radius=0.055, color=gold)
            amount = Text(milestone["label"], font="Arial", font_size=37,
                          weight="BOLD", color=gold if index == len(milestones) - 1 else white)
            amount.scale_to_fit_width(min(amount.width, 2.7))
            y = 1.36 - 0.85 * index
            amount.move_to([3.4 + amount.width / 2, y, 0])
            row = Line([3.4, y - 0.38, 0], [5.98, y - 0.38, 0],
                       color="#244456", stroke_width=1)
            self.play(FadeIn(point), FadeIn(amount, shift=UP * 0.08), FadeIn(row), run_time=0.38)
            previous_age = age
        self.wait(1.2)


if __name__ == "__main__":
    config.media_dir = os.environ.get("MOTION_STUDIO_OUTPUT_DIR", "./media") + "/media"
    config.output_file = "animation"
    GeneratedScene().render()
